import os

DATABASE_UNAVAILABLE_MESSAGE = "database unavailable"

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8002")
DEPENDENCY_TIMEOUT_SECONDS = float(os.getenv("DEPENDENCY_TIMEOUT_SECONDS", "5"))
ORDER_PENDING_TTL_SECONDS = int(os.getenv("ORDER_PENDING_TTL_SECONDS", "300"))
ORDER_CREATE_MAX_IN_FLIGHT = int(os.getenv("ORDER_CREATE_MAX_IN_FLIGHT", "32"))
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")


def db_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL

    if DB_HOST and DB_NAME and DB_USER and DB_PASSWORD:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    return ""


def use_postgres() -> bool:
    return bool(db_url())
