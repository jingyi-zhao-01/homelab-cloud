import json
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from .models import (
    OrderItemOut,
    OrderOut,
    OrderStatus,
    PaymentStatus,
    TerminalizationAction,
    TerminalizationEventType,
)
from .order_storage import (
    StoredOrder,
    StoredTerminalizationTask,
    to_order,
    to_stored_order,
    transition_payment_status,
    transition_status,
)
from .repository_postgres_terminalization import (
    claim_terminalization_tasks as claim_terminalization_tasks_impl,
    ensure_terminalization_tables,
    mark_terminalization_task_retrying as mark_terminalization_task_retrying_impl,
    mark_terminalization_task_succeeded as mark_terminalization_task_succeeded_impl,
    record_terminalization_task_event as record_terminalization_task_event_impl,
    transition_order_and_enqueue_terminalization as transition_order_and_enqueue_terminalization_impl,
)

ROW_FACTORY = cast(Any, dict_row)


class PostgresOrderRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def init_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS orders (
                        id BIGSERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        total_amount NUMERIC(12, 2) NOT NULL,
                        status TEXT NOT NULL DEFAULT 'pending',
                        payment_status TEXT NOT NULL DEFAULT 'pending',
                        idempotency_key TEXT NULL,
                        reservation_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                        items_json JSONB NOT NULL
                    )
                    """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
                    """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS payment_status TEXT NOT NULL DEFAULT 'pending'
                    """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS idempotency_key TEXT NULL
                    """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS reservation_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb
                    """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS orders_idempotency_key_idx
                    ON orders (idempotency_key)
                    WHERE idempotency_key IS NOT NULL
                    """)
                ensure_terminalization_tables(cur)

    def is_healthy(self) -> bool:
        with psycopg.connect(self._database_url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True

    def reset_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE orders RESTART IDENTITY CASCADE")

    def create_order(
        self,
        user_id: int,
        total_amount: float,
        order_items: list[OrderItemOut],
        reservation_ids: list[int],
        idempotency_key: str | None = None,
        status: OrderStatus = "pending",
        payment_status: PaymentStatus = "pending",
    ) -> OrderOut:
        with psycopg.connect(
            self._database_url,
            autocommit=True,
            row_factory=ROW_FACTORY,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (
                        user_id,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                    ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
                    RETURNING
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    """,
                    (
                        user_id,
                        Decimal(str(round(total_amount, 2))),
                        status,
                        payment_status,
                        idempotency_key,
                        json.dumps(reservation_ids),
                        json.dumps([item.model_dump() for item in order_items]),
                    ),
                )
                row = cur.fetchone()
                if row:
                    return to_order(row)
                if idempotency_key:
                    existing = self.get_order_by_idempotency_key(idempotency_key)
                    if existing:
                        return existing
                raise RuntimeError("order persistence failed")

    def update_order_state(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus | None = None,
    ) -> OrderOut | None:
        with psycopg.connect(
            self._database_url,
            autocommit=True,
            row_factory=ROW_FACTORY,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    FROM orders
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                existing = cur.fetchone()
                if not existing:
                    return None
                current_status = cast(OrderStatus, existing["status"])
                current_payment_status = cast(PaymentStatus, existing["payment_status"])
                next_status = transition_status(current_status, status)
                next_payment_status = current_payment_status
                if payment_status is not None:
                    next_payment_status = transition_payment_status(
                        current_payment_status,
                        payment_status,
                    )
                if (
                    next_status == current_status
                    and next_payment_status == current_payment_status
                ):
                    return to_order(existing)

                cur.execute(
                    """
                    UPDATE orders
                    SET status = %s, payment_status = %s
                    WHERE id = %s
                    RETURNING
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    """,
                    (next_status, next_payment_status, order_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return to_order(row)

    def get_order(self, order_id: int) -> OrderOut | None:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    FROM orders
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return to_order(row)

    def get_stored_order(self, order_id: int) -> StoredOrder | None:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    FROM orders
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return to_stored_order(row)

    def get_order_by_idempotency_key(self, idempotency_key: str) -> OrderOut | None:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    FROM orders
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return to_order(row)

    def transition_order_and_enqueue_terminalization(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus,
        action: TerminalizationAction,
        reservation_ids: list[int],
    ) -> OrderOut | None:
        return transition_order_and_enqueue_terminalization_impl(
            database_url=self._database_url,
            order_id=order_id,
            status=status,
            payment_status=payment_status,
            action=action,
            reservation_ids=reservation_ids,
        )

    def claim_terminalization_tasks(
        self,
        limit: int,
        available_before: datetime,
    ) -> list[StoredTerminalizationTask]:
        return claim_terminalization_tasks_impl(
            database_url=self._database_url,
            limit=limit,
            available_before=available_before,
        )

    def mark_terminalization_task_succeeded(self, task_id: int) -> None:
        mark_terminalization_task_succeeded_impl(self._database_url, task_id)

    def mark_terminalization_task_retrying(
        self,
        task_id: int,
        available_at: datetime,
        last_error: str,
    ) -> None:
        mark_terminalization_task_retrying_impl(
            database_url=self._database_url,
            task_id=task_id,
            available_at=available_at,
            last_error=last_error,
        )

    def record_terminalization_task_event(
        self,
        task_id: int,
        order_id: int,
        reservation_id: int,
        action: TerminalizationAction,
        event_type: TerminalizationEventType,
        attempt_count: int,
        last_error: str | None = None,
    ) -> None:
        record_terminalization_task_event_impl(
            database_url=self._database_url,
            task_id=task_id,
            order_id=order_id,
            reservation_id=reservation_id,
            action=action,
            event_type=event_type,
            attempt_count=attempt_count,
            last_error=last_error,
        )

    def list_orders(self) -> list[OrderOut]:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    FROM orders
                    ORDER BY id DESC
                    """)
                rows = cur.fetchall()
                return [to_order(row) for row in rows]

    def list_stale_orders(self, expires_before: datetime) -> list[StoredOrder]:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        user_id,
                        created_at,
                        total_amount,
                        status,
                        payment_status,
                        idempotency_key,
                        reservation_ids_json,
                        items_json
                    FROM orders
                    WHERE status = 'pending' AND created_at <= %s
                    ORDER BY id ASC
                    """,
                    (expires_before,),
                )
                rows = cur.fetchall()
                return [to_stored_order(row) for row in rows]
