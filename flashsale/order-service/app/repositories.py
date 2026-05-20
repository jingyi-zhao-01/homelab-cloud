import json
from datetime import datetime, timezone
from decimal import Decimal
from itertools import count
from threading import Lock
from typing import Any, Protocol, cast

import psycopg
from psycopg.rows import dict_row

from .models import OrderItemOut, OrderOut

ROW_FACTORY = cast(Any, dict_row)


class OrderRepository(Protocol):
    def init_db(self) -> None: ...

    def reset_db(self) -> None: ...

    def create_order(
        self, user_id: int, total_amount: float, order_items: list[OrderItemOut]
    ) -> OrderOut: ...

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
        items=items,
    )


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
        self, user_id: int, total_amount: float, order_items: list[OrderItemOut]
    ) -> OrderOut:
        with self._lock:
            order_id = next(self._counter)
            order = OrderOut(
                id=order_id,
                user_id=user_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                total_amount=round(total_amount, 2),
                items=order_items,
            )
            self._orders[order_id] = order
            return order

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
                        items_json JSONB NOT NULL
                    )
                    """)

    def reset_db(self) -> None:
        with psycopg.connect(self._database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE orders RESTART IDENTITY CASCADE")

    def create_order(
        self, user_id: int, total_amount: float, order_items: list[OrderItemOut]
    ) -> OrderOut:
        with psycopg.connect(
            self._database_url, autocommit=True, row_factory=ROW_FACTORY
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO orders (user_id, total_amount, items_json)
                    VALUES (%s, %s, %s::jsonb)
                    RETURNING id, user_id, created_at, total_amount, items_json
                    """,
                    (
                        user_id,
                        Decimal(str(round(total_amount, 2))),
                        json.dumps([item.model_dump() for item in order_items]),
                    ),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("order persistence failed")
                return _to_order(row)

    def get_order(self, order_id: int) -> OrderOut | None:
        with psycopg.connect(self._database_url, row_factory=ROW_FACTORY) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, created_at, total_amount, items_json
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
                    SELECT id, user_id, created_at, total_amount, items_json
                    FROM orders
                    ORDER BY id DESC
                    """)
                rows = cur.fetchall()
                return [_to_order(row) for row in rows]
