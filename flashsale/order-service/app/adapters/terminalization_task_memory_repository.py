from datetime import datetime
from itertools import count
from threading import Lock

from app.domain.reservation_terminalization_task import (
    ReservationTerminalizationTask,
    ReservationTerminalizationTaskEvent,
)
from app.domain.state_machines import claim_task, set_task_status
from app.domain.statuses import TerminalizationAction, TerminalizationEventType


class TerminalizationTaskMemoryRepository:
    def __init__(self) -> None:
        self._tasks: dict[int, ReservationTerminalizationTask] = {}
        self._events: list[ReservationTerminalizationTaskEvent] = []
        self._task_counter = count(1)
        self._lock = Lock()

    def enqueue(
        self,
        order_id: int,
        reservation_ids: list[int],
        action: TerminalizationAction,
        now: datetime,
    ) -> None:
        with self._lock:
            for reservation_id in reservation_ids:
                task_id = next(self._task_counter)
                task = ReservationTerminalizationTask(
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
                self._tasks[task_id] = task
                self._events.append(
                    ReservationTerminalizationTaskEvent(
                        task_id=task_id,
                        order_id=order_id,
                        reservation_id=reservation_id,
                        action=action,
                        event_type="queued",
                        attempt_count=0,
                        occurred_at=now,
                    )
                )

    def claim_ready(
        self,
        limit: int,
        available_before: datetime,
    ) -> list[ReservationTerminalizationTask]:
        claimed: list[ReservationTerminalizationTask] = []
        with self._lock:
            for task_id in sorted(self._tasks):
                task = self._tasks[task_id]
                if len(claimed) >= limit:
                    break
                if task.status not in {"queued", "retrying"}:
                    continue
                if task.available_at > available_before:
                    continue
                updated = claim_task(task)
                self._tasks[task_id] = updated
                self._events.append(
                    ReservationTerminalizationTaskEvent(
                        task_id=task_id,
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

    def mark_succeeded(self, task_id: int) -> None:
        self._mark(task_id, "succeeded", None)

    def mark_retrying(
        self,
        task_id: int,
        available_at: datetime,
        last_error: str,
    ) -> None:
        with self._lock:
            task = set_task_status(self._tasks[task_id], "retrying", last_error)
            self._tasks[task_id] = ReservationTerminalizationTask(
                **{**task.__dict__, "available_at": available_at}
            )
            self._record_from_task(self._tasks[task_id], "retrying", last_error)

    def record_event(
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
            self._events.append(
                ReservationTerminalizationTaskEvent(
                    task_id=task_id,
                    order_id=order_id,
                    reservation_id=reservation_id,
                    action=action,
                    event_type=event_type,
                    attempt_count=attempt_count,
                    occurred_at=datetime.now(),
                    last_error=last_error,
                )
            )

    def reset(self) -> None:
        with self._lock:
            self._tasks.clear()
            self._events.clear()
            self._task_counter = count(1)

    def _mark(
        self,
        task_id: int,
        status: str,
        last_error: str | None,
    ) -> None:
        with self._lock:
            task = set_task_status(self._tasks[task_id], status, last_error)
            self._tasks[task_id] = task
            self._record_from_task(task, status, last_error)

    def _record_from_task(
        self,
        task: ReservationTerminalizationTask,
        event_type: TerminalizationEventType,
        last_error: str | None,
    ) -> None:
        self._events.append(
            ReservationTerminalizationTaskEvent(
                task_id=task.task_id,
                order_id=task.order_id,
                reservation_id=task.reservation_id,
                action=task.action,
                event_type=event_type,
                attempt_count=task.attempt_count,
                occurred_at=datetime.now(),
                last_error=last_error,
            )
        )
