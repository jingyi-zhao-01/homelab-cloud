from datetime import datetime, timedelta, timezone

from app.application.results import ProcessTerminalizationTasksResult
from app.ports.product_reservation_client import ProductReservationClient
from app.ports.unit_of_work import UnitOfWork


class ProcessTerminalizationTaskUseCase:
    def __init__(
        self,
        uow: UnitOfWork,
        products: ProductReservationClient,
    ) -> None:
        self._uow = uow
        self._products = products

    def process(self, limit: int = 32) -> ProcessTerminalizationTasksResult:
        tasks = self._uow.tasks.claim_ready(
            limit=limit,
            available_before=datetime.now(timezone.utc),
        )
        if not tasks:
            return ProcessTerminalizationTasksResult(0, 0, 0)

        succeeded_count = 0
        retrying_count = 0
        for task in tasks:
            ok, error = self._products.terminalize(task.reservation_id, task.action)
            if ok:
                self._uow.tasks.mark_succeeded(task.task_id)
                succeeded_count += 1
                continue
            retrying_count += 1
            self._uow.tasks.record_event(
                task_id=task.task_id,
                order_id=task.order_id,
                reservation_id=task.reservation_id,
                action=task.action,
                event_type="error",
                attempt_count=task.attempt_count,
                last_error=error,
            )
            self._uow.tasks.mark_retrying(
                task_id=task.task_id,
                available_at=datetime.now(timezone.utc)
                + timedelta(seconds=min(task.attempt_count, 10)),
                last_error=error or "terminalization_failed",
            )

        return ProcessTerminalizationTasksResult(
            claimed_count=len(tasks),
            succeeded_count=succeeded_count,
            retrying_count=retrying_count,
        )
