from datetime import datetime, timedelta, timezone
from threading import Event, Lock, Thread
import logging

import httpx

from .config import DEPENDENCY_TIMEOUT_SECONDS, PRODUCT_SERVICE_URL
from .models import ProcessTerminalizationTasksResult
from .repository_protocol import OrderRepository


class TerminalizationWorker:
    def __init__(
        self,
        repository: OrderRepository,
        logger: logging.Logger,
        storage: str,
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._storage = storage
        self._stop = Event()
        self._lock = Lock()
        self._thread: Thread | None = None

    def start(
        self,
        process_tasks,
        poll_interval_seconds: float = 0.5,
        batch_size: int = 32,
    ) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()

            def _worker_loop() -> None:
                while not self._stop.is_set():
                    try:
                        process_tasks(limit=batch_size)
                    except Exception:
                        self._logger.exception(
                            "event=terminalization_worker_error storage=%s",
                            self._storage,
                        )
                    self._stop.wait(poll_interval_seconds)

            self._thread = Thread(
                target=_worker_loop,
                name="order-terminalization-worker",
                daemon=True,
            )
            self._thread.start()
            self._logger.info(
                "event=terminalization_worker_started storage=%s batch_size=%s poll_interval_seconds=%.2f",
                self._storage,
                batch_size,
                poll_interval_seconds,
            )

    def stop(self, join_timeout_seconds: float = 2.0) -> None:
        with self._lock:
            if not self._thread:
                return
            self._stop.set()
            self._thread.join(timeout=join_timeout_seconds)
            self._thread = None
            self._logger.info(
                "event=terminalization_worker_stopped storage=%s",
                self._storage,
            )


def process_terminalization_tasks(
    repository: OrderRepository,
    logger: logging.Logger,
    storage: str,
    limit: int = 32,
) -> ProcessTerminalizationTasksResult:
    tasks = repository.claim_terminalization_tasks(
        limit=limit,
        available_before=datetime.now(timezone.utc),
    )
    if not tasks:
        return ProcessTerminalizationTasksResult(
            claimed_count=0,
            succeeded_count=0,
            retrying_count=0,
        )

    succeeded_count = 0
    retrying_count = 0
    with httpx.Client() as client:
        for task in tasks:
            try:
                response = client.post(
                    f"{PRODUCT_SERVICE_URL}/reservations/{task.reservation_id}/{task.action}",
                    timeout=DEPENDENCY_TIMEOUT_SECONDS,
                )
                if response.status_code >= 400:
                    next_attempt_at = datetime.now(timezone.utc) + timedelta(
                        seconds=min(task.attempt_count, 10)
                    )
                    repository.mark_terminalization_task_retrying(
                        task.task_id,
                        available_at=next_attempt_at,
                        last_error=f"status_code={response.status_code}",
                    )
                    retrying_count += 1
                    logger.warning(
                        "event=terminalization_task_retry task_id=%s order_id=%s reservation_id=%s action=%s status_code=%s attempt_count=%s storage=%s",
                        task.task_id,
                        task.order_id,
                        task.reservation_id,
                        task.action,
                        response.status_code,
                        task.attempt_count,
                        storage,
                    )
                    continue

                repository.mark_terminalization_task_succeeded(task.task_id)
                succeeded_count += 1
                logger.info(
                    "event=terminalization_task_succeeded task_id=%s order_id=%s reservation_id=%s action=%s attempt_count=%s storage=%s",
                    task.task_id,
                    task.order_id,
                    task.reservation_id,
                    task.action,
                    task.attempt_count,
                    storage,
                )
            except Exception as exc:
                next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=min(task.attempt_count, 10)
                )
                repository.mark_terminalization_task_retrying(
                    task.task_id,
                    available_at=next_attempt_at,
                    last_error=exc.__class__.__name__,
                )
                retrying_count += 1
                logger.exception(
                    "event=terminalization_task_error task_id=%s order_id=%s reservation_id=%s action=%s attempt_count=%s storage=%s",
                    task.task_id,
                    task.order_id,
                    task.reservation_id,
                    task.action,
                    task.attempt_count,
                    storage,
                )

    return ProcessTerminalizationTasksResult(
        claimed_count=len(tasks),
        succeeded_count=succeeded_count,
        retrying_count=retrying_count,
    )
