from datetime import datetime, timezone
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from .models import (
    OrderOut,
    OrderStatus,
    PaymentStatus,
    TerminalizationAction,
    TerminalizationEventType,
)
from .order_storage import (
    StoredTerminalizationTask,
    to_order,
    to_stored_terminalization_task,
    transition_payment_status,
    transition_status,
)

ROW_FACTORY = cast(Any, dict_row)


def ensure_terminalization_tables(cur: Any) -> None:
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_terminalization_task_events (
            event_id BIGSERIAL PRIMARY KEY,
            task_id BIGINT NOT NULL REFERENCES order_terminalization_tasks(task_id) ON DELETE CASCADE,
            order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            reservation_id BIGINT NOT NULL,
            action TEXT NOT NULL,
            event_type TEXT NOT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NULL,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS order_terminalization_task_events_lookup_idx
        ON order_terminalization_task_events (occurred_at, event_type, action, task_id)
        """)


def transition_order_and_enqueue_terminalization(
    database_url: str,
    order_id: int,
    status: OrderStatus,
    payment_status: PaymentStatus,
    action: TerminalizationAction,
    reservation_ids: list[int],
) -> OrderOut | None:
    with psycopg.connect(database_url, row_factory=ROW_FACTORY) as conn:
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
                    RETURNING task_id
                    """,
                    (order_id, reservation_id, action, now, now),
                )
                task_row = cur.fetchone()
                if not task_row:
                    raise RuntimeError("terminalization task persistence failed")
                record_terminalization_task_event(
                    database_url=database_url,
                    task_id=int(task_row["task_id"]),
                    order_id=order_id,
                    reservation_id=reservation_id,
                    action=action,
                    event_type="queued",
                    attempt_count=0,
                    occurred_at=now,
                    cursor=cur,
                )
            conn.commit()
            return to_order(updated)


def claim_terminalization_tasks(
    database_url: str,
    limit: int,
    available_before: datetime,
) -> list[StoredTerminalizationTask]:
    with psycopg.connect(database_url, row_factory=ROW_FACTORY) as conn:
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
            now = datetime.now(timezone.utc)
            for row in rows:
                record_terminalization_task_event(
                    database_url=database_url,
                    task_id=int(row["task_id"]),
                    order_id=int(row["order_id"]),
                    reservation_id=int(row["reservation_id"]),
                    action=row["action"],
                    event_type="processing",
                    attempt_count=int(row["attempt_count"]),
                    last_error=row["last_error"],
                    occurred_at=now,
                    cursor=cur,
                )
            conn.commit()
            return [to_stored_terminalization_task(row) for row in rows]


def mark_terminalization_task_succeeded(database_url: str, task_id: int) -> None:
    with psycopg.connect(database_url, autocommit=True, row_factory=ROW_FACTORY) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT task_id, order_id, reservation_id, action, attempt_count
                FROM order_terminalization_tasks
                WHERE task_id = %s
                """,
                (task_id,),
            )
            task = cur.fetchone()
            if not task:
                return
            cur.execute(
                """
                UPDATE order_terminalization_tasks
                SET status = 'succeeded',
                    last_error = NULL
                WHERE task_id = %s
                """,
                (task_id,),
            )
            record_terminalization_task_event(
                database_url=database_url,
                task_id=int(task["task_id"]),
                order_id=int(task["order_id"]),
                reservation_id=int(task["reservation_id"]),
                action=task["action"],
                event_type="succeeded",
                attempt_count=int(task["attempt_count"]),
                cursor=cur,
            )


def mark_terminalization_task_retrying(
    database_url: str,
    task_id: int,
    available_at: datetime,
    last_error: str,
) -> None:
    with psycopg.connect(database_url, autocommit=True, row_factory=ROW_FACTORY) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT task_id, order_id, reservation_id, action, attempt_count
                FROM order_terminalization_tasks
                WHERE task_id = %s
                """,
                (task_id,),
            )
            task = cur.fetchone()
            if not task:
                return
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
            record_terminalization_task_event(
                database_url=database_url,
                task_id=int(task["task_id"]),
                order_id=int(task["order_id"]),
                reservation_id=int(task["reservation_id"]),
                action=task["action"],
                event_type="retrying",
                attempt_count=int(task["attempt_count"]),
                last_error=last_error,
                cursor=cur,
            )


def record_terminalization_task_event(
    database_url: str,
    task_id: int,
    order_id: int,
    reservation_id: int,
    action: TerminalizationAction,
    event_type: TerminalizationEventType,
    attempt_count: int,
    last_error: str | None = None,
    occurred_at: datetime | None = None,
    cursor: Any | None = None,
) -> None:
    values = (
        task_id,
        order_id,
        reservation_id,
        action,
        event_type,
        attempt_count,
        last_error,
        occurred_at,
    )
    if cursor is not None:
        cursor.execute(
            """
            INSERT INTO order_terminalization_task_events (
                task_id,
                order_id,
                reservation_id,
                action,
                event_type,
                attempt_count,
                last_error,
                occurred_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
            """,
            values,
        )
        return

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO order_terminalization_task_events (
                    task_id,
                    order_id,
                    reservation_id,
                    action,
                    event_type,
                    attempt_count,
                    last_error,
                    occurred_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
                """,
                values,
            )
