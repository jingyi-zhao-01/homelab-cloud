import logging
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
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

from app.models import OrderCreateRequest, PaymentWebhookRequest
from app.repositories import InMemoryOrderRepository, StoredOrder
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
            if self.product_state.reservations.get(reservation_id) == "reserved":
                self.product_state.reservations[reservation_id] = "cancelled"
                self.product_state.stock += 1
            return FakeResponse(
                200,
                {
                    "reservation_id": reservation_id,
                    "product_id": 42,
                    "quantity": 1,
                    "unit_price": self.product_state.price,
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
                    "unit_price": self.product_state.price,
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
            reservation_ids=[],
            status="pending",
        )

        confirmed = repository.update_order_state(order.id, "confirmed")

        self.assertIsNotNone(confirmed)
        self.assertEqual(order.status, "pending")
        self.assertEqual(confirmed.status, "confirmed")
        self.assertEqual(confirmed.payment_status, "pending")

    def test_order_status_rejects_invalid_transition(self) -> None:
        repository = InMemoryOrderRepository()
        order = repository.create_order(
            user_id=1,
            total_amount=9.99,
            order_items=[],
            reservation_ids=[],
            status="pending",
        )
        repository.update_order_state(order.id, "confirmed", payment_status="succeeded")

        with self.assertRaises(ValueError):
            repository.update_order_state(order.id, "failed", payment_status="cancelled")


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
        self.assertEqual(order.payment_status, "succeeded")
        self.assertEqual(persisted.status, "confirmed")
        self.assertEqual(persisted.payment_status, "succeeded")
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
        self.assertEqual(orders[0].payment_status, "cancelled")
        self.assertEqual(product_state.stock, product_state.initial_stock)
        self.assertEqual(product_state.reservations[1], "cancelled")

    def test_out_of_stock_returns_conflict_and_does_not_persist_order(self) -> None:
        product_state = FakeProductState(stock=0, price=9.99)

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            with self.assertRaises(HTTPException) as exc_info:
                self.service.create_order(self.payload)

        self.assertEqual(exc_info.exception.status_code, 409)
        self.assertEqual(self.repository.list_orders(), [])
        self.assertEqual(product_state.stock, 0)

    def test_idempotency_key_returns_existing_order_without_second_reserve(self) -> None:
        product_state = FakeProductState(stock=5, price=9.99)
        payload = OrderCreateRequest(
            user_id=1,
            idempotency_key="flashsale-key-1",
            items=[{"product_id": 42, "quantity": 1}],
        )

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            first = self.service.create_order(payload)
            second = self.service.create_order(payload)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.status, "confirmed")
        self.assertEqual(second.status, "confirmed")
        self.assertEqual(product_state.stock, 4)
        self.assertEqual(len(product_state.reservations), 1)

    def test_expire_orders_cancels_pending_order_and_releases_inventory(self) -> None:
        product_state = FakeProductState(stock=4, price=9.99)
        product_state.reservations[1] = "reserved"
        order = self.repository.create_order(
            user_id=1,
            total_amount=9.99,
            order_items=[],
            reservation_ids=[1],
            idempotency_key="stale-key",
            status="pending",
            payment_status="pending",
        )
        stale_created_at = (
            datetime.now(timezone.utc) - timedelta(seconds=301)
        ).isoformat()
        stored = self.repository._orders[order.id]
        self.repository._orders[order.id] = StoredOrder(
            order=stored.order.model_copy(update={"created_at": stale_created_at}),
            reservation_ids=stored.reservation_ids,
        )

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            result = self.service.expire_orders()

        expired_order = self.repository.get_order(order.id)
        self.assertEqual(result.expired_count, 1)
        self.assertIsNotNone(expired_order)
        self.assertEqual(expired_order.status, "expired")
        self.assertEqual(expired_order.payment_status, "cancelled")
        self.assertEqual(product_state.stock, 5)
        self.assertEqual(product_state.reservations[1], "cancelled")

    def test_duplicate_payment_webhook_is_idempotent(self) -> None:
        product_state = FakeProductState(stock=4, price=9.99)
        product_state.reservations[1] = "reserved"
        order = self.repository.create_order(
            user_id=1,
            total_amount=9.99,
            order_items=[],
            reservation_ids=[1],
            idempotency_key="payment-order",
            status="pending",
            payment_status="pending",
        )
        payload = PaymentWebhookRequest(order_id=order.id, event_id="evt-1")

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            first = self.service.process_payment_webhook(payload)
            second = self.service.process_payment_webhook(payload)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.status, "confirmed")
        self.assertEqual(first.payment_status, "succeeded")
        self.assertEqual(second.status, "confirmed")
        self.assertEqual(second.payment_status, "succeeded")
        self.assertEqual(product_state.stock, 4)
        self.assertEqual(product_state.reservations[1], "confirmed")

    def test_payment_success_after_timeout_race_keeps_order_expired(self) -> None:
        product_state = FakeProductState(stock=4, price=9.99)
        product_state.reservations[1] = "reserved"
        order = self.repository.create_order(
            user_id=1,
            total_amount=9.99,
            order_items=[],
            reservation_ids=[1],
            idempotency_key="timeout-race",
            status="pending",
            payment_status="pending",
        )
        stale_created_at = (
            datetime.now(timezone.utc) - timedelta(seconds=301)
        ).isoformat()
        stored = self.repository._orders[order.id]
        self.repository._orders[order.id] = StoredOrder(
            order=stored.order.model_copy(update={"created_at": stale_created_at}),
            reservation_ids=stored.reservation_ids,
        )
        payload = PaymentWebhookRequest(order_id=order.id, event_id="evt-timeout")

        with patch("app.service.httpx.Client", return_value=FakeHttpClient(product_state)):
            self.service.expire_orders()
            raced = self.service.process_payment_webhook(payload)

        self.assertEqual(raced.status, "expired")
        self.assertEqual(raced.payment_status, "cancelled")
        self.assertEqual(product_state.stock, 5)
        self.assertEqual(product_state.reservations[1], "cancelled")


if __name__ == "__main__":
    unittest.main()
