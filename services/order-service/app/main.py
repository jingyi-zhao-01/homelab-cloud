from fastapi import FastAPI

from .config import db_url, use_postgres
from .models import OrderCreateRequest, OrderOut
from .observability import configure_service_logger, create_request_logging_middleware
from .repositories import InMemoryOrderRepository, PostgresOrderRepository
from .service import OrderService

SERVICE_NAME = "order-service"
logger = configure_service_logger(SERVICE_NAME)

app = FastAPI(title=SERVICE_NAME, version="0.1.0")
app.middleware("http")(create_request_logging_middleware(logger, SERVICE_NAME))

if use_postgres():
    repository = PostgresOrderRepository(db_url())
    storage = "postgres"
else:
    repository = InMemoryOrderRepository()
    storage = "memory"

order_service = OrderService(repository=repository, logger=logger, storage=storage)


@app.on_event("startup")
def startup() -> None:
    logger.info("event=startup service=%s", SERVICE_NAME)
    try:
        order_service.init_db()
    except Exception:
        # Keep service available even if DB startup checks fail.
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post(
    "/orders",
    status_code=201,
    responses={
        400: {"description": "Order items cannot be empty"},
        404: {"description": "User or product not found"},
        409: {"description": "Insufficient product stock"},
        502: {"description": "Dependent service unavailable"},
        503: {"description": "Database unavailable"},
    },
)
def create_order(payload: OrderCreateRequest) -> OrderOut:
    return order_service.create_order(payload)


@app.get(
    "/orders/{order_id}",
    responses={
        404: {"description": "Order not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_order(order_id: int) -> OrderOut:
    return order_service.get_order(order_id)


@app.get(
    "/orders",
    responses={503: {"description": "Database unavailable"}},
)
def list_orders() -> list[OrderOut]:
    return order_service.list_orders()
