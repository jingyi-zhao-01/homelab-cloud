from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from .models import (
    TerminalizationEventType,
    OrderItemOut,
    OrderOut,
    OrderStatus,
    PaymentStatus,
    TerminalizationAction,
    TerminalizationTaskStatus,
)


@dataclass(frozen=True)
class StoredOrder:
    order: OrderOut
    reservation_ids: tuple[int, ...]


@dataclass(frozen=True)
class StoredTerminalizationTask:
    task_id: int
    order_id: int
    reservation_id: int
    action: TerminalizationAction
    status: TerminalizationTaskStatus
    attempt_count: int
    available_at: datetime
    created_at: datetime
    last_error: str | None


@dataclass(frozen=True)
class StoredTerminalizationTaskEvent:
    event_id: int
    task_id: int
    order_id: int
    reservation_id: int
    action: TerminalizationAction
    event_type: TerminalizationEventType
    attempt_count: int
    occurred_at: datetime
    last_error: str | None


def to_order(row: Any) -> OrderOut:
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


def to_stored_order(row: Any) -> StoredOrder:
    return StoredOrder(
        order=to_order(row),
        reservation_ids=tuple(int(value) for value in row["reservation_ids_json"]),
    )


def to_stored_terminalization_task(row: Any) -> StoredTerminalizationTask:
    return StoredTerminalizationTask(
        task_id=int(row["task_id"]),
        order_id=int(row["order_id"]),
        reservation_id=int(row["reservation_id"]),
        action=cast(TerminalizationAction, row["action"]),
        status=cast(TerminalizationTaskStatus, row["status"]),
        attempt_count=int(row["attempt_count"]),
        available_at=cast(datetime, row["available_at"]),
        created_at=cast(datetime, row["created_at"]),
        last_error=cast(str | None, row["last_error"]),
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


def transition_status(current: OrderStatus, target: OrderStatus) -> OrderStatus:
    if target == current:
        return current
    if target not in ALLOWED_ORDER_TRANSITIONS[current]:
        raise ValueError(f"invalid order status transition: {current} -> {target}")
    return target


def transition_payment_status(
    current: PaymentStatus, target: PaymentStatus
) -> PaymentStatus:
    if target == current:
        return current
    if target not in ALLOWED_PAYMENT_TRANSITIONS[current]:
        raise ValueError(
            f"invalid payment status transition: {current} -> {target}"
        )
    return target
