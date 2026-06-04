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

ROW_FACTORY = cast(Any, dict_row)


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
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
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
                conn.commit()
                return to_order(row)
