import os
from decimal import Decimal
from datetime import datetime, timezone
from itertools import count
from threading import Lock
from typing import Any
import json

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import psycopg
from psycopg.rows import dict_row

app = FastAPI(title="order-service", version="0.1.0")

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8001")
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8002")
DB_HOST = os.getenv("DB_HOST", "")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_UNAVAILABLE_MESSAGE = "database unavailable"


class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreateRequest(BaseModel):
    user_id: int
    items: list[OrderItemRequest]


class OrderItemOut(BaseModel):
    product_id: int
    quantity: int
    unit_price: float
    line_total: float


class OrderOut(BaseModel):
    id: int
    user_id: int
    created_at: str
    total_amount: float
    items: list[OrderItemOut]


_orders: dict[int, OrderOut] = {}
_counter = count(1)
_lock = Lock()


def _use_postgres() -> bool:
    return bool(_db_url())


def _db_url() -> str:
    if DATABASE_URL:
        return DATABASE_URL

    if DB_HOST and DB_NAME and DB_USER and DB_PASSWORD:
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    return ""


def _init_db() -> None:
    if not _use_postgres():
        return

    with psycopg.connect(_db_url(), autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    total_amount NUMERIC(12, 2) NOT NULL,
                    items_json JSONB NOT NULL
                )
                """)


def _to_order(row: dict[str, Any]) -> OrderOut:
    items = [OrderItemOut.model_validate(item) for item in row["items_json"]]
    created_at = row["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()

    return OrderOut(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        created_at=created_at,
        total_amount=float(row["total_amount"]),
        items=items,
    )


@app.on_event("startup")
def startup() -> None:
    try:
        _init_db()
    except Exception:
        # Keep service available even if DB startup checks fail.
        pass


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "order-service"}


def _ensure_user_exists(client: httpx.Client, user_id: int) -> None:
    response = client.get(f"{USER_SERVICE_URL}/users/{user_id}", timeout=5)
    if response.status_code == 404:
        raise HTTPException(status_code=404, detail="user not found")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="user-service unavailable")


def _reserve_and_price_item(
    client: httpx.Client, product_id: int, quantity: int
) -> tuple[float, int]:
    product_response = client.get(
        f"{PRODUCT_SERVICE_URL}/products/{product_id}", timeout=5
    )
    if product_response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"product {product_id} not found")
    if product_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="product-service unavailable")

    price = float(product_response.json()["price"])

    reserve_response = client.post(
        f"{PRODUCT_SERVICE_URL}/products/{product_id}/reserve",
        json={"quantity": quantity},
        timeout=5,
    )
    if reserve_response.status_code == 409:
        raise HTTPException(
            status_code=409,
            detail=f"insufficient stock for product {product_id}",
        )
    if reserve_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="product reserve failed")

    return price, quantity


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
    if not payload.items:
        raise HTTPException(status_code=400, detail="order items cannot be empty")

    with httpx.Client() as client:
        _ensure_user_exists(client=client, user_id=payload.user_id)

        order_items: list[OrderItemOut] = []
        total_amount = 0.0

        for item in payload.items:
            unit_price, quantity = _reserve_and_price_item(
                client=client,
                product_id=item.product_id,
                quantity=item.quantity,
            )
            line_total = unit_price * quantity
            total_amount += line_total
            order_items.append(
                OrderItemOut(
                    product_id=item.product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )

    if _use_postgres():
        try:
            with psycopg.connect(
                _db_url(), autocommit=True, row_factory=dict_row
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO orders (user_id, total_amount, items_json)
                        VALUES (%s, %s, %s::jsonb)
                        RETURNING id, user_id, created_at, total_amount, items_json
                        """,
                        (
                            payload.user_id,
                            Decimal(str(round(total_amount, 2))),
                            json.dumps([item.model_dump() for item in order_items]),
                        ),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(
                            status_code=503, detail="order persistence failed"
                        )
                    return _to_order(row)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    with _lock:
        order_id = next(_counter)
        order = OrderOut(
            id=order_id,
            user_id=payload.user_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            total_amount=round(total_amount, 2),
            items=order_items,
        )
        _orders[order_id] = order
        return order


@app.get(
    "/orders/{order_id}",
    responses={
        404: {"description": "Order not found"},
        503: {"description": "Database unavailable"},
    },
)
def get_order(order_id: int) -> OrderOut:
    if _use_postgres():
        try:
            with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, user_id, created_at, total_amount, items_json
                        FROM orders
                        WHERE id = %s
                        """,
                        (order_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise HTTPException(status_code=404, detail="order not found")
                    return _to_order(row)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    order = _orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="order not found")
    return order


@app.get(
    "/orders",
    responses={503: {"description": "Database unavailable"}},
)
def list_orders() -> list[OrderOut]:
    if _use_postgres():
        try:
            with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, user_id, created_at, total_amount, items_json
                        FROM orders
                        ORDER BY id DESC
                        """)
                    rows = cur.fetchall()
                    return [_to_order(row) for row in rows]
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    return list(_orders.values())
