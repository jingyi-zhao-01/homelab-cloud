import json
from datetime import datetime, timezone
from decimal import Decimal
from itertools import count
from threading import Lock
from typing import Any, Protocol, cast

import psycopg
from psycopg.rows import dict_row

from .models import OrderItemOut, OrderOut, OrderStatus

ROW_FACTORY = cast(Any, dict_row)


class OrderRepository(Protocol):
    def init_db(self) -> None: ...

    def reset_db(self) -> None: ...

    def create_order(
        self,
        user_id: int,
        total_amount: float,
        order_items: list[OrderItemOut],
        status: OrderStatus = "pending",
    ) -> OrderOut: ...

    def update_order_status(
        self, order_id: int, status: OrderStatus
    ) -> OrderOut | None: ...

    def get_order(self, order_id: int) -> OrderOut | None: ...

    def list_orders(self) -> list[OrderOut]: ...


def _to_order(row: Any) -> OrderOut:
    items = [OrderItemOut.model_validate(item) for item in row["items_json"]]
    created_at = row["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()

    return OrderOut(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        created_at=created_at,
        total_amount=float(row["total_amount"]),
        status=cast(OrderStatus, row["status"]),
        items=items,
    )


ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    "pending": {"confirmed", "failed"},
    "confirmed": {"confirmed"},
    "failed": {"failed"},
}


def _transition_status(current: OrderStatus, target: OrderStatus) -> OrderStatus:
    if target == current:
        return current
    if target not in ALLOWED_ORDER_TRANSITIONS[current]:
        raise ValueError(f"invalid order status transition: {current} -> {target}")
    return target


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: dict[int, OrderOut] = {}
        self._counter = count(1)
        self._lock = Lock()

    def init_db(self) -> None:
        return

    def reset_db(self) -> None:
        with self._lock:
            self._orders.clear()
            self._counter = count(1)

    def create_order(
        self,
        user_id: int,
        total_amount: float,
        order_items: list[OrderItemOut],
        status: OrderStatus = "pending",
    ) -> OrderOut:
        with self._lock:
            order_id = next(self._counter)
            order = OrderOut(
                id=order_id,
                user_id=user_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                total_amount=round(total_amount, 2),
                status=status,
                items=order_items,
            )
            self._orders[order_id] = order
            return order

    def update_order_status(
        self, order_id: int, status: OrderStatus
    ) -> OrderOut | None:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            next_status = _transition_status(order.status, status)
            updated = order.model_copy(update={"status": next_status})
            self._orders[order_id] = updated
            return updated

    def get_order(self, order_id: int) -> OrderOut | None:
        return self._orders.get(order_id)

    def list_orders(self) -> list[OrderOut]:
        return list(self._orders.values())


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
                        items_json JSONB NOT NULL
                    )
                    """)
                cur.execute("""
                    ALTER TABLE orders
                    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'pending'
                    """)

    def reset_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE orders RESTART IDENTITY CASCADE")

    def create_order(
        self,
        user_id: int,
        total_amount: float,
        order_items: list[OrderItemOut],
        status: OrderStatus = "pending",
    ) -> OrderOut:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=ROW_FACTORY
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (user_id, total_amount, status, items_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    RETURNING id, user_id, created_at, total_amount, status, items_json
                    """,
                    (
                        user_id,
                        Decimal(str(round(total_amount, 2))),
                        status,
                        json.dumps([item.model_dump() for item in order_items]),
                    ),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("order persistence failed")
                return _to_order(row)

    def update_order_status(
        self, order_id: int, status: OrderStatus
    ) -> OrderOut | None:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=ROW_FACTORY
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, created_at, total_amount, status, items_json
                    FROM orders
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                existing = cur.fetchone()
                if not existing:
                    return None
                current_status = cast(OrderStatus, existing["status"])
                next_status = _transition_status(current_status, status)
                if next_status == current_status:
                    return _to_order(existing)

                cur.execute(
                    """
                    UPDATE orders
                    SET status = %s
                    WHERE id = %s
                    RETURNING id, user_id, created_at, total_amount, status, items_json
                    """,
                    (next_status, order_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return _to_order(row)

    def get_order(self, order_id: int) -> OrderOut | None:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, created_at, total_amount, status, items_json
                    FROM orders
                    WHERE id = %s
                    """,
                    (order_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return _to_order(row)

    def list_orders(self) -> list[OrderOut]:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, user_id, created_at, total_amount, status, items_json
                    FROM orders
                    ORDER BY id DESC
                    """)
                rows = cur.fetchall()
                return [_to_order(row) for row in rows]
