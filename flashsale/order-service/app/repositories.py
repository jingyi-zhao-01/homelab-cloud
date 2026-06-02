import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from itertools import count
from threading import Lock
from typing import Any, Protocol, cast

import psycopg
from psycopg.rows import dict_row

from .models import OrderItemOut, OrderOut, OrderStatus, PaymentStatus

ROW_FACTORY = cast(Any, dict_row)


@dataclass(frozen=True)
class StoredOrder:
    order: OrderOut
    reservation_ids: tuple[int, ...]


class OrderRepository(Protocol):
    def init_db(self) -> None: ...

    def reset_db(self) -> None: ...

    def create_order(
        self,
        user_id: int,
        total_amount: float,
        order_items: list[OrderItemOut],
        reservation_ids: list[int],
        idempotency_key: str | None = None,
        status: OrderStatus = "pending",
        payment_status: PaymentStatus = "pending",
    ) -> OrderOut: ...

    def update_order_state(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus | None = None,
    ) -> OrderOut | None: ...

    def get_stored_order(self, order_id: int) -> StoredOrder | None: ...

    def get_order(self, order_id: int) -> OrderOut | None: ...

    def get_order_by_idempotency_key(self, idempotency_key: str) -> OrderOut | None: ...

    def list_orders(self) -> list[OrderOut]: ...

    def list_stale_orders(self, expires_before: datetime) -> list[StoredOrder]: ...


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
        payment_status=cast(PaymentStatus, row["payment_status"]),
        idempotency_key=cast(str | None, row["idempotency_key"]),
        items=items,
    )


def _to_stored_order(row: Any) -> StoredOrder:
    return StoredOrder(
        order=_to_order(row),
        reservation_ids=tuple(int(value) for value in row["reservation_ids_json"]),
    )


ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    "pending": {"confirmed", "failed", "cancelled", "expired"},
    "confirmed": {"confirmed"},
    "failed": {"failed"},
    "cancelled": {"cancelled"},
    "expired": {"expired"},
}

ALLOWED_PAYMENT_TRANSITIONS: dict[PaymentStatus, set[PaymentStatus]] = {
    "pending": {"succeeded", "cancelled"},
    "succeeded": {"succeeded"},
    "cancelled": {"cancelled"},
}


def _transition_status(current: OrderStatus, target: OrderStatus) -> OrderStatus:
    if target == current:
        return current
    if target not in ALLOWED_ORDER_TRANSITIONS[current]:
        raise ValueError(f"invalid order status transition: {current} -> {target}")
    return target


def _transition_payment_status(
    current: PaymentStatus, target: PaymentStatus
) -> PaymentStatus:
    if target == current:
        return current
    if target not in ALLOWED_PAYMENT_TRANSITIONS[current]:
        raise ValueError(
            f"invalid payment status transition: {current} -> {target}"
        )
    return target


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: dict[int, StoredOrder] = {}
        self._idempotency_keys: dict[str, int] = {}
        self._counter = count(1)
        self._lock = Lock()

    def init_db(self) -> None:
        return

    def reset_db(self) -> None:
        with self._lock:
            self._orders.clear()
            self._idempotency_keys.clear()
            self._counter = count(1)

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
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_keys:
                existing_id = self._idempotency_keys[idempotency_key]
                return self._orders[existing_id].order

            order_id = next(self._counter)
            order = OrderOut(
                id=order_id,
                user_id=user_id,
                created_at=datetime.now(timezone.utc).isoformat(),
                total_amount=round(total_amount, 2),
                status=status,
                payment_status=payment_status,
                idempotency_key=idempotency_key,
                items=order_items,
            )
            self._orders[order_id] = StoredOrder(
                order=order,
                reservation_ids=tuple(reservation_ids),
            )
            if idempotency_key:
                self._idempotency_keys[idempotency_key] = order_id
            return order

    def update_order_state(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus | None = None,
    ) -> OrderOut | None:
        with self._lock:
            stored = self._orders.get(order_id)
            if not stored:
                return None
            next_status = _transition_status(stored.order.status, status)
            next_payment_status = stored.order.payment_status
            if payment_status is not None:
                next_payment_status = _transition_payment_status(
                    stored.order.payment_status, payment_status
                )
            updated = stored.order.model_copy(
                update={
                    "status": next_status,
                    "payment_status": next_payment_status,
                }
            )
            self._orders[order_id] = StoredOrder(
                order=updated,
                reservation_ids=stored.reservation_ids,
            )
            return updated

    def get_order(self, order_id: int) -> OrderOut | None:
        stored = self._orders.get(order_id)
        return stored.order if stored else None

    def get_stored_order(self, order_id: int) -> StoredOrder | None:
        return self._orders.get(order_id)

    def get_order_by_idempotency_key(self, idempotency_key: str) -> OrderOut | None:
        order_id = self._idempotency_keys.get(idempotency_key)
        if order_id is None:
            return None
        stored = self._orders.get(order_id)
        return stored.order if stored else None

    def list_orders(self) -> list[OrderOut]:
        return [stored.order for stored in self._orders.values()]

    def list_stale_orders(self, expires_before: datetime) -> list[StoredOrder]:
        stale_orders: list[StoredOrder] = []
        for stored in self._orders.values():
            if stored.order.status != "pending":
                continue
            created_at = datetime.fromisoformat(stored.order.created_at)
            if created_at <= expires_before:
                stale_orders.append(stored)
        return stale_orders


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
            self._database_url, autocommit=True, row_factory=ROW_FACTORY
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
                    return _to_order(row)
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
            self._database_url, autocommit=True, row_factory=ROW_FACTORY
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
                current_payment_status = cast(
                    PaymentStatus, existing["payment_status"]
                )
                next_status = _transition_status(current_status, status)
                next_payment_status = current_payment_status
                if payment_status is not None:
                    next_payment_status = _transition_payment_status(
                        current_payment_status, payment_status
                    )
                if (
                    next_status == current_status
                    and next_payment_status == current_payment_status
                ):
                    return _to_order(existing)

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
                return _to_order(row)

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
                return _to_order(row)

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
                return _to_stored_order(row)

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
                return _to_order(row)

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
                return [_to_order(row) for row in rows]

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
                return [_to_stored_order(row) for row in rows]
