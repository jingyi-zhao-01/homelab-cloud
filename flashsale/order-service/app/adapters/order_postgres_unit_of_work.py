import logging
import time
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from app.adapters.order_postgres_repository import OrderPostgresRepository
from app.adapters.order_postgres_rows import to_order
from app.adapters.order_postgres_schema import (
    ensure_order_tables,
    ensure_terminalization_tables,
)
from app.adapters.terminalization_task_postgres_repository import TerminalizationTaskPostgresRepository
from app.domain.order import Order
from app.domain.state_machines import transition_order
from app.domain.statuses import OrderStatus, PaymentStatus, TerminalizationAction
from app.observability import start_span

ROW_FACTORY = cast(Any, dict_row)
db_logger = logging.getLogger("order-service.db")


class OrderPostgresUnitOfWork:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self.orders = OrderPostgresRepository(database_url)
        self.tasks = TerminalizationTaskPostgresRepository(database_url)

    def init_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                ensure_order_tables(cur)
                ensure_terminalization_tables(cur)

    def is_healthy(self) -> bool:
        with psycopg.connect(self._database_url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True

    def reset(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE orders RESTART IDENTITY CASCADE")

    def finalize_order(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus,
        action: TerminalizationAction,
        reservation_ids: list[int],
    ) -> Order | None:
        order_update_ms = 0.0
        enqueue_task_ms = 0.0
        total_start = time.perf_counter()
        with start_span(
            "order-service",
            "order db finalize and enqueue",
            attributes={
                "db.system": "postgresql",
                "flashsale.order_id": order_id,
                "flashsale.action": action,
                "flashsale.reservation_count": len(reservation_ids),
            },
        ):
            with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
                with conn.cursor() as cur:
                    update_start = time.perf_counter()
                    cur.execute(
                        """
                        SELECT id, user_id, created_at, total_amount, status,
                               payment_status, idempotency_key, reservation_ids_json, items_json
                        FROM orders
                        WHERE id = %s
                        FOR UPDATE
                        """,
                        (order_id,),
                    )
                    current = cur.fetchone()
                    if not current:
                        return None
                    updated = transition_order(to_order(current), status, payment_status)
                    cur.execute(
                        """
                        UPDATE orders
                        SET status = %s, payment_status = %s
                        WHERE id = %s
                        RETURNING id, user_id, created_at, total_amount, status,
                                  payment_status, idempotency_key, reservation_ids_json, items_json
                        """,
                        (updated.status, updated.payment_status, order_id),
                    )
                    row = cur.fetchone()
                    order_update_ms = (time.perf_counter() - update_start) * 1000
                    enqueue_start = time.perf_counter()
                    for reservation_id in reservation_ids:
                        cur.execute(
                            """
                            INSERT INTO order_terminalization_tasks (
                                order_id, reservation_id, action, status, attempt_count
                            ) VALUES (%s, %s, %s, 'queued', 0)
                            RETURNING task_id
                            """,
                            (order_id, reservation_id, action),
                        )
                        task = cur.fetchone()
                        cur.execute(
                            """
                            INSERT INTO order_terminalization_task_events (
                                task_id, order_id, reservation_id, action, event_type, attempt_count
                            ) VALUES (%s, %s, %s, %s, 'queued', 0)
                            """,
                            (task["task_id"], order_id, reservation_id, action),
                        )
                    enqueue_task_ms = (time.perf_counter() - enqueue_start) * 1000
                    conn.commit()
                    db_logger.info(
                        "event=order_service_enqueue_task order_id=%s action=%s reservation_count=%s "
                        "order_db_ms=%.2f enqueue_task_ms=%.2f total_finalize_ms=%.2f result=success",
                        order_id,
                        action,
                        len(reservation_ids),
                        order_update_ms,
                        enqueue_task_ms,
                        (time.perf_counter() - total_start) * 1000,
                    )
                    return to_order(row)
