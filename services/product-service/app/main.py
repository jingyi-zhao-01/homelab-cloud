import os
from itertools import count
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row

app = FastAPI(title="product-service", version="0.1.0")

DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_UNAVAILABLE_MESSAGE = "database unavailable"
PRODUCT_NOT_FOUND_MESSAGE = "product not found"
DEFAULT_SEED_PRODUCT_COUNT = 100


class ProductCreate(BaseModel):
    name: str
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    stock: int


class ReserveRequest(BaseModel):
    quantity: int = Field(gt=0)


_products: dict[int, ProductOut] = {}
_counter = count(1)
_lock = Lock()


def _seed_items(
    count_value: int = DEFAULT_SEED_PRODUCT_COUNT,
) -> list[tuple[str, float, int]]:
    return [
        (
            f"Seed Item {idx}",
            round(9.9 + idx * 0.5, 2),
            10 + (idx % 15),
        )
        for idx in range(1, count_value + 1)
    ]


def _db_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL

    if DB_HOST and DB_NAME and DB_USER and DB_PASSWORD:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    return ""


def _use_postgres() -> bool:
    return bool(_db_url())


def _init_db() -> None:
    if not _use_postgres():
        return

    with psycopg.connect(_db_url(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    price NUMERIC(12, 2) NOT NULL,
                    stock INTEGER NOT NULL CHECK (stock >= 0)
                )
                """)


def _to_product(row: dict[str, Any]) -> ProductOut:
    return ProductOut(
        id=int(row["id"]),
        name=str(row["name"]),
        price=float(row["price"]),
        stock=int(row["stock"]),
    )


def _seed_products_db_if_empty() -> None:
    with psycopg.connect(_db_url(), autocommit=True, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS count FROM products")
            row = cur.fetchone()
            if not row or int(row["count"]) > 0:
                return

            cur.executemany(
                """
                INSERT INTO products (name, price, stock)
                VALUES (%s, %s, %s)
                """,
                _seed_items(),
            )


def _seed_products_memory_if_empty() -> None:
    global _counter

    with _lock:
        if _products:
            return

        for idx, (name, price, stock) in enumerate(_seed_items(), start=1):
            _products[idx] = ProductOut(id=idx, name=name, price=price, stock=stock)

        _counter = count(len(_products) + 1)


@app.on_event("startup")
def startup() -> None:
    try:
        _init_db()
        if _use_postgres():
            _seed_products_db_if_empty()
        else:
            _seed_products_memory_if_empty()
    except Exception:
        # Keep service available even if DB startup checks fail.
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "product-service"}


@app.post(
    "/products",
    status_code=201,
    responses={503: {"description": "Database unavailable"}},
)
def create_product(payload: ProductCreate) -> ProductOut:
    if _use_postgres():
        try:
            with psycopg.connect(
                _db_url(), autocommit=True, row_factory=dict_row
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO products (name, price, stock)
                        VALUES (%s, %s, %s)
                        RETURNING id, name, price, stock
                        """,
                        (payload.name, payload.price, payload.stock),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(
                            status_code=503, detail="product persistence failed"
                        )
                    return _to_product(row)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    with _lock:
        product_id = next(_counter)
        product = ProductOut(
            id=product_id,
            name=payload.name,
            price=payload.price,
            stock=payload.stock,
        )
        _products[product_id] = product
    return product


@app.get(
    "/products/{product_id}",
    responses={
        404: {"description": "Product not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_product(product_id: int) -> ProductOut:
    if _use_postgres():
        try:
            with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, name, price, stock
                        FROM products
                        WHERE id = %s
                        """,
                        (product_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(
                            status_code=404, detail=PRODUCT_NOT_FOUND_MESSAGE
                        )
                    return _to_product(row)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    product = _products.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MESSAGE)
    return product


@app.post(
    "/products/{product_id}/reserve",
    responses={
        404: {"description": "Product not found"},
        409: {"description": "Insufficient stock"},
        503: {"description": "Database unavailable"},
    },
)
def reserve_product(product_id: int, payload: ReserveRequest) -> ProductOut:
    if _use_postgres():
        try:
            with psycopg.connect(
                _db_url(), autocommit=True, row_factory=dict_row
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE products
                        SET stock = stock - %s
                        WHERE id = %s AND stock >= %s
                        RETURNING id, name, price, stock
                        """,
                        (payload.quantity, product_id, payload.quantity),
                    )
                    updated = cur.fetchone()
                    if updated:
                        return _to_product(updated)

                    cur.execute("SELECT id FROM products WHERE id = %s", (product_id,))
                    exists = cur.fetchone()
                    if not exists:
                        raise HTTPException(
                            status_code=404, detail=PRODUCT_NOT_FOUND_MESSAGE
                        )
                    raise HTTPException(status_code=409, detail="insufficient stock")
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    with _lock:
        product = _products.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MESSAGE)

        if product.stock < payload.quantity:
            raise HTTPException(status_code=409, detail="insufficient stock")

        updated = ProductOut(
            id=product.id,
            name=product.name,
            price=product.price,
            stock=product.stock - payload.quantity,
        )
        _products[product_id] = updated
    return updated


@app.get(
    "/products",
    responses={503: {"description": "Database unavailable"}},
)
def list_products() -> list[ProductOut]:
    if _use_postgres():
        try:
            with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, name, price, stock
                        FROM products
                        ORDER BY id DESC
                        """)
                    rows = cur.fetchall()
                    return [_to_product(row) for row in rows]
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    return list(_products.values())
