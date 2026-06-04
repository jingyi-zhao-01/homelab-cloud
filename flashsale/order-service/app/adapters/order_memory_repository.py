from dataclasses import replace
from datetime import datetime, timezone
from itertools import count
from threading import Lock

from app.domain.order import Order, OrderItem
from app.domain.state_machines import transition_order
from app.domain.statuses import OrderStatus, PaymentStatus


class OrderMemoryRepository:
    def __init__(self) -> None:
        self._orders: dict[int, Order] = {}
        self._idempotency_keys: dict[str, int] = {}
        self._counter = count(1)
        self._lock = Lock()

    def create(
        self,
        user_id: int,
        total_amount: float,
        items: list[OrderItem],
        reservation_ids: list[int],
        idempotency_key: str | None = None,
        status: OrderStatus = "pending",
        payment_status: PaymentStatus = "pending",
    ) -> Order:
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency_keys:
                return self._orders[self._idempotency_keys[idempotency_key]]
            order_id = next(self._counter)
            order = Order(
                id=order_id,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                total_amount=round(total_amount, 2),
                status=status,
                payment_status=payment_status,
                idempotency_key=idempotency_key,
                items=tuple(items),
                reservation_ids=tuple(reservation_ids),
            )
            self._orders[order_id] = order
            if idempotency_key:
                self._idempotency_keys[idempotency_key] = order_id
            return order

    def update_state(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus | None = None,
    ) -> Order | None:
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                return None
            updated = transition_order(order, status, payment_status)
            self._orders[order_id] = updated
            return updated

    def replace_order(self, order: Order) -> None:
        with self._lock:
            self._orders[order.id] = order

    def get(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Order | None:
        order_id = self._idempotency_keys.get(idempotency_key)
        return self._orders.get(order_id) if order_id is not None else None

    def list_all(self) -> list[Order]:
        return list(self._orders.values())

    def list_stale(self, expires_before: datetime) -> list[Order]:
        return [
            order
            for order in self._orders.values()
            if order.status == "pending" and order.created_at <= expires_before
        ]

    def reset(self) -> None:
        with self._lock:
            self._orders.clear()
            self._idempotency_keys.clear()
            self._counter = count(1)

    def override_created_at(self, order_id: int, created_at: datetime) -> None:
        with self._lock:
            self._orders[order_id] = replace(
                self._orders[order_id],
                created_at=created_at,
            )
