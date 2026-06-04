from datetime import datetime, timezone

from app.adapters.order_memory_repository import OrderMemoryRepository
from app.adapters.terminalization_task_memory_repository import (
    TerminalizationTaskMemoryRepository,
)
from app.domain.order import Order
from app.domain.state_machines import transition_order
from app.domain.statuses import OrderStatus, PaymentStatus, TerminalizationAction


class OrderMemoryUnitOfWork:
    def __init__(self) -> None:
        self.orders = OrderMemoryRepository()
        self.tasks = TerminalizationTaskMemoryRepository()

    def init_db(self) -> None:
        return

    def is_healthy(self) -> bool:
        return True

    def reset(self) -> None:
        self.orders.reset()
        self.tasks.reset()

    def finalize_order(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus,
        action: TerminalizationAction,
        reservation_ids: list[int],
    ) -> Order | None:
        order = self.orders.get(order_id)
        if not order:
            return None
        updated = transition_order(order, status, payment_status)
        self.orders.replace_order(updated)
        self.tasks.enqueue(
            order_id=order_id,
            reservation_ids=reservation_ids,
            action=action,
            now=datetime.now(timezone.utc),
        )
        return updated
