import anyio
from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse

from .config import db_url, use_postgres
from .models import (
    ErrorResponse,
    ExpireOrdersResult,
    HealthResponse,
    OrderCreateRequest,
    OrderOut,
    PaymentWebhookRequest,
)
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
probe_limiter = anyio.CapacityLimiter(8)


@app.on_event("startup")
def startup() -> None:
    logger.info("event=startup service=%s", SERVICE_NAME)
    try:
        order_service.init_db()
    except Exception:
        # Keep service available even if DB startup checks fail.
        pass


async def _repository_is_healthy() -> bool:
    try:
        return await anyio.to_thread.run_sync(
            repository.is_healthy,
            limiter=probe_limiter,
        )
    except Exception:
        logger.warning("event=healthcheck_failed service=%s", SERVICE_NAME, exc_info=True)
        return False


@app.get(
    "/health",
    summary="Service health check",
    description="Returns readiness for order-service, including database reachability.",
    tags=["system"],
)
async def health() -> HealthResponse:
    healthy = await _repository_is_healthy()
    if not healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=HealthResponse(status="database-unavailable", service=SERVICE_NAME).model_dump(),
        )
    return HealthResponse(status="ok", service=SERVICE_NAME)


@app.get(
    "/live",
    summary="Service liveness check",
    description="Returns basic process liveness for order-service without touching dependencies.",
    tags=["system"],
)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME)


@app.post(
    "/orders",
    status_code=201,
    summary="Create order",
    description="Validates the user, reserves product stock, and persists a new order.",
    tags=["orders"],
    responses={
        400: {"model": ErrorResponse, "description": "Order items cannot be empty"},
        404: {"model": ErrorResponse, "description": "User or product not found"},
        409: {"model": ErrorResponse, "description": "Insufficient product stock"},
        502: {"model": ErrorResponse, "description": "Dependent service unavailable"},
        503: {"model": ErrorResponse, "description": "Database unavailable"},
    },
)
def create_order(payload: OrderCreateRequest) -> OrderOut:
    return order_service.create_order(payload)


@app.get(
    "/orders/{order_id}",
    summary="Get order",
    description="Fetches a single order by identifier.",
    tags=["orders"],
    responses={
        404: {"model": ErrorResponse, "description": "Order not found"},
        503: {"model": ErrorResponse, "description": "Database unavailable"},
    },
)
def get_order(order_id: int) -> OrderOut:
    return order_service.get_order(order_id)


@app.get(
    "/orders",
    summary="List orders",
    description="Returns all persisted orders visible to the service storage backend.",
    tags=["orders"],
    responses={503: {"model": ErrorResponse, "description": "Database unavailable"}},
)
def list_orders() -> list[OrderOut]:
    return order_service.list_orders()


@app.post(
    "/payments/webhook",
    summary="Process payment webhook",
    description="Applies a successful payment event to the referenced order.",
    tags=["payments"],
    responses={
        404: {"model": ErrorResponse, "description": "Order not found"},
        503: {"model": ErrorResponse, "description": "Database unavailable"},
    },
)
def payment_webhook(payload: PaymentWebhookRequest) -> OrderOut:
    return order_service.process_payment_webhook(payload)


@app.post(
    "/admin/reset",
    status_code=204,
    summary="Reset order storage",
    description="Clears order-service backing storage for local and integration test workflows.",
    tags=["admin"],
    responses={503: {"model": ErrorResponse, "description": "Database unavailable"}},
)
def admin_reset() -> Response:
    order_service._repository.reset_db()
    return Response(status_code=204)


@app.post(
    "/admin/expire-orders",
    summary="Expire pending orders",
    description="Marks elapsed pending orders as expired and releases their reservations.",
    tags=["admin"],
    responses={503: {"model": ErrorResponse, "description": "Database unavailable"}},
)
def admin_expire_orders() -> ExpireOrdersResult:
    return order_service.expire_orders()
