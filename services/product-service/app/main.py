from fastapi import FastAPI

from .config import SEED_PRODUCT_COUNT, SEED_PRODUCT_QUANTITY, db_url, use_postgres
from .models import ProductCreate, ProductOut, ReserveRequest
from .observability import configure_service_logger, create_request_logging_middleware
from .repositories import InMemoryProductRepository, PostgresProductRepository
from .service import ProductService

SERVICE_NAME = "product-service"
logger = configure_service_logger(SERVICE_NAME)

app = FastAPI(title=SERVICE_NAME, version="0.1.0")
app.middleware("http")(create_request_logging_middleware(logger, SERVICE_NAME))

if use_postgres():
    repository = PostgresProductRepository(db_url())
    storage = "postgres"
else:
    repository = InMemoryProductRepository()
    storage = "memory"

product_service = ProductService(repository=repository, logger=logger, storage=storage)


@app.on_event("startup")
def startup() -> None:
    logger.info("event=startup service=%s", SERVICE_NAME)
    try:
        product_service.startup()
    except Exception:
        # Keep service available even if DB startup checks fail.
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.post(
    "/products",
    status_code=201,
    responses={503: {"description": "Database unavailable"}},
)
def create_product(payload: ProductCreate) -> ProductOut:
    return product_service.create_product(payload)


@app.get(
    "/products/{product_id}",
    responses={
        404: {"description": "Product not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_product(product_id: int) -> ProductOut:
    return product_service.get_product(product_id)


@app.post(
    "/products/{product_id}/reserve",
    responses={
        404: {"description": "Product not found"},
        409: {"description": "Insufficient stock"},
        503: {"description": "Database unavailable"},
    },
)
def reserve_product(product_id: int, payload: ReserveRequest) -> ProductOut:
    return product_service.reserve_product(product_id, payload)


@app.get(
    "/products",
    responses={503: {"description": "Database unavailable"}},
)
def list_products() -> list[ProductOut]:
    return product_service.list_products()


@app.post(
    "/admin/reset",
    status_code=204,
    responses={503: {"description": "Database unavailable"}},
)
def admin_reset() -> None:
    product_service._repository.reset_db()


@app.post(
    "/admin/seed",
    status_code=204,
    responses={503: {"description": "Database unavailable"}},
)
def admin_seed() -> None:
    product_service._repository.seed_with_quantity(
        SEED_PRODUCT_COUNT, SEED_PRODUCT_QUANTITY
    )
