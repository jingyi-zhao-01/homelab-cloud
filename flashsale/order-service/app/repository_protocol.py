from datetime import datetime
from typing import Protocol

from .models import (
    OrderItemOut,
    OrderOut,
    OrderStatus,
    PaymentStatus,
    TerminalizationAction,
)
from .order_storage import StoredOrder, StoredTerminalizationTask


class OrderRepository(Protocol):
    def init_db(self) -> None: ...

    def is_healthy(self) -> bool: ...

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

    def transition_order_and_enqueue_terminalization(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus,
        action: TerminalizationAction,
        reservation_ids: list[int],
    ) -> OrderOut | None: ...

    def claim_terminalization_tasks(
        self,
        limit: int,
        available_before: datetime,
    ) -> list[StoredTerminalizationTask]: ...

    def mark_terminalization_task_succeeded(self, task_id: int) -> None: ...

    def mark_terminalization_task_retrying(
        self,
        task_id: int,
        available_at: datetime,
        last_error: str,
    ) -> None: ...

    def list_orders(self) -> list[OrderOut]: ...

    def list_stale_orders(self, expires_before: datetime) -> list[StoredOrder]: ...
