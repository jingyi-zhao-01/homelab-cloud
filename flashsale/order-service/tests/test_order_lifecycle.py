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

from app.models import OrderCreateRequest
from app.repositories import InMemoryOrderRepository
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
        self.next_reservation_id = 1
        self.reservations: dict[int, str] = {}


class FakeHttpClient:
    def __init__(self, product_state: FakeProductState, confirm_status_code: int = 200) -> None:
        self.product_state = product_state
        self.confirm_status_code = confirm_status_code

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

    def post(
        self, url: str, json: dict[str, object] | None = None, timeout: float = 0
    ) -> FakeResponse:
        if url.endswith("/reserve"):
            if json is None:
                raise AssertionError("reserve requires json payload")
            quantity = int(json["quantity"])
            if self.product_state.stock < quantity:
                return FakeResponse(409, {"detail": "insufficient stock"})
            self.product_state.stock -= quantity
            reservation_id = self.product_state.next_reservation_id
            self.product_state.next_reservation_id += 1
            self.product_state.reservations[reservation_id] = "reserved"
            return FakeResponse(
                200,
                {
                    "reservation_id": reservation_id,
                    "product_id": 42,
                    "quantity": quantity,
                    "status": "reserved",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            )
        if "/reservations/" in url and url.endswith("/cancel"):
            reservation_id = int(url.rstrip("/").split("/")[-2])
            if self.product_state.reservations.get(reservation_id) == "reserved":
                self.product_state.reservations[reservation_id] = "cancelled"
                self.product_state.stock += 1
            return FakeResponse(
                200,
                {
                    "reservation_id": reservation_id,
                    "product_id": 42,
                    "quantity": 1,
                    "status": self.product_state.reservations.get(
                        reservation_id, "cancelled"
                    ),
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            )
        if "/reservations/" in url and url.endswith("/confirm"):
            reservation_id = int(url.rstrip("/").split("/")[-2])
            if self.confirm_status_code >= 400:
                return FakeResponse(self.confirm_status_code, {"detail": "confirm failed"})
            self.product_state.reservations[reservation_id] = "confirmed"
            return FakeResponse(
                200,
                {
                    "reservation_id": reservation_id,
                    "product_id": 42,
                    "quantity": 1,
                    "status": "confirmed",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            )
        raise AssertionError(f"unexpected POST url: {url}")


class OrderRepositoryStateMachineTest(unittest.TestCase):
    def test_order_status_transitions_pending_to_confirmed(self) -> None:
        repository = InMemoryOrderRepository()
        order = repository.create_order(
            user_id=1,
            total_amount=9.99,
            order_items=[],
            status="pending",
        )

        confirmed = repository.update_order_status(order.id, "confirmed")

        self.assertIsNotNone(confirmed)
        self.assertEqual(order.status, "pending")
        self.assertEqual(confirmed.status, "confirmed")

    def test_order_status_rejects_invalid_transition(self) -> None:
        repository = InMemoryOrderRepository()
        order = repository.create_order(
            user_id=1,
            total_amount=9.99,
            order_items=[],
            status="pending",
        )
        repository.update_order_status(order.id, "confirmed")

        with self.assertRaises(ValueError):
            repository.update_order_status(order.id, "failed")


class OrderServiceLifecycleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = InMemoryOrderRepository()
        self.service = OrderService(
            repository=self.repository,
            logger=logging.getLogger("test-order-service"),
            storage="test",
        )
        self.payload = OrderCreateRequest(
            user_id=1,
            items=[{"product_id": 42, "quantity": 1}],
        )

    def test_successful_order_is_confirmed(self) -> None:
        product_state = FakeProductState(stock=5, price=9.99)

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            order = self.service.create_order(self.payload)

        persisted = self.repository.get_order(order.id)
        self.assertIsNotNone(persisted)
        self.assertEqual(order.status, "confirmed")
        self.assertEqual(persisted.status, "confirmed")
        self.assertEqual(product_state.stock, 4)
        self.assertEqual(product_state.reservations[1], "confirmed")

    def test_confirm_failure_marks_order_failed_and_releases_inventory(self) -> None:
        product_state = FakeProductState(stock=5, price=9.99)

        with patch(
            "app.service.httpx.Client",
            return_value=FakeHttpClient(product_state, confirm_status_code=502),
        ):
            with self.assertRaises(HTTPException) as exc_info:
                self.service.create_order(self.payload)

        self.assertEqual(exc_info.exception.status_code, 502)
        orders = self.repository.list_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].status, "failed")
        self.assertEqual(product_state.stock, product_state.initial_stock)
        self.assertEqual(product_state.reservations[1], "cancelled")


if __name__ == "__main__":
    unittest.main()
