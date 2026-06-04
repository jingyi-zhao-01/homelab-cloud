import logging
import sys
import types
import unittest
from datetime import datetime, timezone
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
        self.next_reservation_id = 1
        self.reservations: dict[int, str] = {}


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
                    "unit_price": self.product_state.price,
                    "status": "reserved",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            )
        if "/reservations/" in url and url.endswith("/cancel"):
            reservation_id = int(url.rstrip("/").split("/")[-2])
            quantity = 1
            if self.product_state.reservations.get(reservation_id) == "reserved":
                self.product_state.reservations[reservation_id] = "cancelled"
                self.product_state.stock += quantity
            return FakeResponse(
                200,
                {
                    "reservation_id": reservation_id,
                    "product_id": 42,
                    "quantity": quantity,
                    "unit_price": self.product_state.price,
                    "status": "cancelled",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            )
        if "/reservations/" in url and url.endswith("/confirm"):
            reservation_id = int(url.rstrip("/").split("/")[-2])
            quantity = 1
            self.product_state.reservations[reservation_id] = "confirmed"
            return FakeResponse(
                200,
                {
                    "reservation_id": reservation_id,
                    "product_id": 42,
                    "quantity": quantity,
                    "unit_price": self.product_state.price,
                    "status": "confirmed",
                    "expires_at": "2099-01-01T00:00:00+00:00",
                },
            )
        raise AssertionError(f"unexpected POST url: {url}")


class FailingOrderRepository:
    def __init__(self) -> None:
        self.created_orders: list[dict[str, object]] = []

    def init_db(self) -> None:
        return None

    def create_order(
        self,
        user_id: int,
        total_amount: float,
        order_items: list[OrderItemOut],
        reservation_ids: list[int],
        idempotency_key: str | None = None,
        status: str = "pending",
        payment_status: str = "pending",
    ) -> None:
        self.created_orders.append(
            {
                "user_id": user_id,
                "total_amount": total_amount,
                "order_items": order_items,
                "reservation_ids": reservation_ids,
                "idempotency_key": idempotency_key,
                "status": status,
                "payment_status": payment_status,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        raise RuntimeError("simulated persistence failure")

    def get_order(self, order_id: int) -> None:
        return None

    def get_order_by_idempotency_key(self, idempotency_key: str) -> None:
        return None

    def transition_order_and_enqueue_terminalization(
        self,
        order_id: int,
        status: str,
        payment_status: str,
        action: str,
        reservation_ids: list[int],
    ) -> None:
        return None

    def claim_terminalization_tasks(self, limit: int, available_before) -> list[object]:
        return []

    def mark_terminalization_task_succeeded(self, task_id: int) -> None:
        return None

    def mark_terminalization_task_retrying(
        self, task_id: int, available_at, last_error: str
    ) -> None:
        return None

    def list_orders(self) -> list[object]:
        return []

    def list_stale_orders(self, expires_before) -> list[object]:
        return []

    def update_order_state(
        self, order_id: int, status: str, payment_status: str | None = None
    ) -> None:
        return None


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
