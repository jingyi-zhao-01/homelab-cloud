import logging
import sys
import types
import unittest
from unittest.mock import patch

psycopg_stub = types.ModuleType("psycopg")
psycopg_rows_stub = types.ModuleType("psycopg.rows")


class _PsycopgError(Exception):
    pass


psycopg_stub.Error = _PsycopgError
psycopg_stub.connect = None
psycopg_rows_stub.dict_row = object()

sys.modules.setdefault("psycopg", psycopg_stub)
sys.modules.setdefault("psycopg.rows", psycopg_rows_stub)

from fastapi import HTTPException

from app.models import OrderCreateRequest, OrderItemOut
from app.service import OrderService


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


class FakeProductState:
    def __init__(self, stock: int, price: float) -> None:
        self.initial_stock = stock
        self.stock = stock
        self.price = price


class FakeHttpClient:
    def __init__(self, product_state: FakeProductState) -> None:
        self.product_state = product_state

    def __enter__(self) -> "FakeHttpClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def get(self, url: str, timeout: float) -> FakeResponse:
        if "/users/" in url:
            return FakeResponse(200, {"id": 1})
        if "/products/" in url:
            return FakeResponse(
                200,
                {
                    "id": 42,
                    "name": "flashsale item",
                    "price": self.product_state.price,
                    "stock": self.product_state.stock,
                },
            )
        raise AssertionError(f"unexpected GET url: {url}")

    def post(self, url: str, json: dict[str, object], timeout: float) -> FakeResponse:
        if not url.endswith("/reserve"):
            raise AssertionError(f"unexpected POST url: {url}")

        quantity = int(json["quantity"])
        if self.product_state.stock < quantity:
            return FakeResponse(409, {"detail": "insufficient stock"})

        self.product_state.stock -= quantity
        return FakeResponse(
            200,
            {
                "id": 42,
                "name": "flashsale item",
                "price": self.product_state.price,
                "stock": self.product_state.stock,
            },
        )


class FailingOrderRepository:
    def init_db(self) -> None:
        return None

    def create_order(
        self, user_id: int, total_amount: float, order_items: list[OrderItemOut]
    ) -> None:
        raise RuntimeError("simulated persistence failure")

    def get_order(self, order_id: int) -> None:
        return None

    def list_orders(self) -> list[object]:
        return []


class OrderPersistenceFailureConsistencyTest(unittest.TestCase):
    def test_persistence_failure_does_not_consume_inventory(self) -> None:
        product_state = FakeProductState(stock=5, price=9.99)
        service = OrderService(
            repository=FailingOrderRepository(),
            logger=logging.getLogger("test-order-service"),
            storage="test",
        )

        payload = OrderCreateRequest(
            user_id=1,
            items=[{"product_id": 42, "quantity": 1}],
        )

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            with self.assertRaises(HTTPException) as exc_info:
                service.create_order(payload)

        self.assertEqual(exc_info.exception.status_code, 503)
        self.assertEqual(
            product_state.stock,
            product_state.initial_stock,
            "inventory changed even though order persistence failed",
        )


if __name__ == "__main__":
    unittest.main()
