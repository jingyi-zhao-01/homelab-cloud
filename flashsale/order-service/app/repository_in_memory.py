from datetime import datetime, timezone
from itertools import count
from threading import Lock

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
    StoredTerminalizationTaskEvent,
    transition_payment_status,
    transition_status,
)


class InMemoryOrderRepository:
    def __init__(self) -> None:
        self._orders: dict[int, StoredOrder] = {}
        self._idempotency_keys: dict[str, int] = {}
        self._terminalization_tasks: dict[int, StoredTerminalizationTask] = {}
        self._terminalization_task_events: list[StoredTerminalizationTaskEvent] = []
        self._counter = count(1)
        self._task_counter = count(1)
        self._event_counter = count(1)
        self._lock = Lock()

    def init_db(self) -> None:
        return

    def is_healthy(self) -> bool:
        return True

    def reset_db(self) -> None:
        with self._lock:
            self._orders.clear()
            self._idempotency_keys.clear()
            self._terminalization_tasks.clear()
            self._terminalization_task_events.clear()
            self._counter = count(1)
            self._task_counter = count(1)
            self._event_counter = count(1)

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
            next_status = transition_status(stored.order.status, status)
            next_payment_status = stored.order.payment_status
            if payment_status is not None:
                next_payment_status = transition_payment_status(
                    stored.order.payment_status,
                    payment_status,
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

    def transition_order_and_enqueue_terminalization(
        self,
        order_id: int,
        status: OrderStatus,
        payment_status: PaymentStatus,
        action: TerminalizationAction,
        reservation_ids: list[int],
    ) -> OrderOut | None:
        with self._lock:
            stored = self._orders.get(order_id)
            if not stored:
                return None
            next_status = transition_status(stored.order.status, status)
            next_payment_status = transition_payment_status(
                stored.order.payment_status,
                payment_status,
            )
            updated = stored.order.model_copy(
                update={
                    "status": next_status,
                    "payment_status": next_payment_status,
                }
            )
            now = datetime.now(timezone.utc)
            for reservation_id in reservation_ids:
                task_id = next(self._task_counter)
                self._terminalization_tasks[task_id] = StoredTerminalizationTask(
                    task_id=task_id,
                    order_id=order_id,
                    reservation_id=reservation_id,
                    action=action,
                    status="queued",
                    attempt_count=0,
                    available_at=now,
                    created_at=now,
                    last_error=None,
                )
                self._terminalization_task_events.append(
                    StoredTerminalizationTaskEvent(
                        event_id=next(self._event_counter),
                        task_id=task_id,
                        order_id=order_id,
                        reservation_id=reservation_id,
                        action=action,
                        event_type="queued",
                        attempt_count=0,
                        occurred_at=now,
                        last_error=None,
                    )
                )
            self._orders[order_id] = StoredOrder(
                order=updated,
                reservation_ids=stored.reservation_ids,
            )
            return updated

    def claim_terminalization_tasks(
        self,
        limit: int,
        available_before: datetime,
    ) -> list[StoredTerminalizationTask]:
        claimed: list[StoredTerminalizationTask] = []
        with self._lock:
            for task_id in sorted(self._terminalization_tasks):
                if len(claimed) >= limit:
                    break
                task = self._terminalization_tasks[task_id]
                if task.status not in {"queued", "retrying"}:
                    continue
                if task.available_at > available_before:
                    continue
                updated = StoredTerminalizationTask(
                    task_id=task.task_id,
                    order_id=task.order_id,
                    reservation_id=task.reservation_id,
                    action=task.action,
                    status="processing",
                    attempt_count=task.attempt_count + 1,
                    available_at=task.available_at,
                    created_at=task.created_at,
                    last_error=task.last_error,
                )
                self._terminalization_tasks[task_id] = updated
                self._terminalization_task_events.append(
                    StoredTerminalizationTaskEvent(
                        event_id=next(self._event_counter),
                        task_id=updated.task_id,
                        order_id=updated.order_id,
                        reservation_id=updated.reservation_id,
                        action=updated.action,
                        event_type="processing",
                        attempt_count=updated.attempt_count,
                        occurred_at=available_before,
                        last_error=updated.last_error,
                    )
                )
                claimed.append(updated)
        return claimed

    def mark_terminalization_task_succeeded(self, task_id: int) -> None:
        with self._lock:
            task = self._terminalization_tasks[task_id]
            self._terminalization_tasks[task_id] = StoredTerminalizationTask(
                task_id=task.task_id,
                order_id=task.order_id,
                reservation_id=task.reservation_id,
                action=task.action,
                status="succeeded",
                attempt_count=task.attempt_count,
                available_at=task.available_at,
                created_at=task.created_at,
                last_error=None,
            )
            self._terminalization_task_events.append(
                StoredTerminalizationTaskEvent(
                    event_id=next(self._event_counter),
                    task_id=task.task_id,
                    order_id=task.order_id,
                    reservation_id=task.reservation_id,
                    action=task.action,
                    event_type="succeeded",
                    attempt_count=task.attempt_count,
                    occurred_at=datetime.now(timezone.utc),
                    last_error=None,
                )
            )

    def mark_terminalization_task_retrying(
        self,
        task_id: int,
        available_at: datetime,
        last_error: str,
    ) -> None:
        with self._lock:
            task = self._terminalization_tasks[task_id]
            self._terminalization_tasks[task_id] = StoredTerminalizationTask(
                task_id=task.task_id,
                order_id=task.order_id,
                reservation_id=task.reservation_id,
                action=task.action,
                status="retrying",
                attempt_count=task.attempt_count,
                available_at=available_at,
                created_at=task.created_at,
                last_error=last_error,
            )
            self._terminalization_task_events.append(
                StoredTerminalizationTaskEvent(
                    event_id=next(self._event_counter),
                    task_id=task.task_id,
                    order_id=task.order_id,
                    reservation_id=task.reservation_id,
                    action=task.action,
                    event_type="retrying",
                    attempt_count=task.attempt_count,
                    occurred_at=datetime.now(timezone.utc),
                    last_error=last_error,
                )
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
        with self._lock:
            self._terminalization_task_events.append(
                StoredTerminalizationTaskEvent(
                    event_id=next(self._event_counter),
                    task_id=task_id,
                    order_id=order_id,
                    reservation_id=reservation_id,
                    action=action,
                    event_type=event_type,
                    attempt_count=attempt_count,
                    occurred_at=datetime.now(timezone.utc),
                    last_error=last_error,
                )
            )

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
