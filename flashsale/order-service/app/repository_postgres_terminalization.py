from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType


def _load_queue_module() -> ModuleType:
    queue_path = Path(__file__).resolve().parent.parent / "queue.py"
    spec = spec_from_file_location("order_service_queue_module", queue_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load queue module from {queue_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_QUEUE = _load_queue_module()

ensure_terminalization_tables = _QUEUE.ensure_terminalization_tables
transition_order_and_enqueue_terminalization = (
    _QUEUE.transition_order_and_enqueue_terminalization
)
claim_terminalization_tasks = _QUEUE.claim_terminalization_tasks
mark_terminalization_task_succeeded = _QUEUE.mark_terminalization_task_succeeded
mark_terminalization_task_retrying = _QUEUE.mark_terminalization_task_retrying
record_terminalization_task_event = _QUEUE.record_terminalization_task_event
