import json
from datetime import datetime, timezone
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
)
from .order_storage import (
    StoredOrder,
    StoredTerminalizationTask,
    to_order,
    to_stored_order,
    to_stored_terminalization_task,
    transition_payment_status,
    transition_status,
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS order_terminalization_tasks (
                        task_id BIGSERIAL PRIMARY KEY,
                        order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                        reservation_id BIGINT NOT NULL,
                        action TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'queued',
                        attempt_count INTEGER NOT NULL DEFAULT 0,
                        available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        last_error TEXT NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS order_terminalization_tasks_ready_idx
                    ON order_terminalization_tasks (status, available_at, task_id)
                    """)

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
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                existing = cur.fetchone()
                if not existing:
                    return None
                current_status = cast(OrderStatus, existing["status"])
                current_payment_status = cast(PaymentStatus, existing["payment_status"])
                next_status = transition_status(current_status, status)
                next_payment_status = transition_payment_status(
                    current_payment_status,
                    payment_status,
                )
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
                updated = cur.fetchone()
                if not updated:
                    return None
                now = datetime.now(timezone.utc)
                for reservation_id in reservation_ids:
                    cur.execute(
                        """
                        INSERT INTO order_terminalization_tasks (
                            order_id,
                            reservation_id,
                            action,
                            status,
                            attempt_count,
                            available_at,
                            created_at
                        )
                        VALUES (%s, %s, %s, 'queued', 0, %s, %s)
                        """,
                        (order_id, reservation_id, action, now, now),
                    )
                conn.commit()
                return to_order(updated)

    def claim_terminalization_tasks(
        self,
        limit: int,
        available_before: datetime,
    ) -> list[StoredTerminalizationTask]:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    WITH ready AS (
                        SELECT task_id
                        FROM order_terminalization_tasks
                        WHERE status IN ('queued', 'retrying')
                          AND available_at <= %s
                        ORDER BY task_id ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT %s
                    )
                    UPDATE order_terminalization_tasks tasks
                    SET status = 'processing',
                        attempt_count = attempt_count + 1
                    FROM ready
                    WHERE tasks.task_id = ready.task_id
                    RETURNING
                        tasks.task_id,
                        tasks.order_id,
                        tasks.reservation_id,
                        tasks.action,
                        tasks.status,
                        tasks.attempt_count,
                        tasks.available_at,
                        tasks.last_error,
                        tasks.created_at
                    """,
                    (available_before, limit),
                )
                rows = cur.fetchall()
                conn.commit()
                return [to_stored_terminalization_task(row) for row in rows]

    def mark_terminalization_task_succeeded(self, task_id: int) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE order_terminalization_tasks
                    SET status = 'succeeded',
                        last_error = NULL
                    WHERE task_id = %s
                    """,
                    (task_id,),
                )

    def mark_terminalization_task_retrying(
        self,
        task_id: int,
        available_at: datetime,
        last_error: str,
    ) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE order_terminalization_tasks
                    SET status = 'retrying',
                        available_at = %s,
                        last_error = %s
                    WHERE task_id = %s
                    """,
                    (available_at, last_error, task_id),
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
