import logging

import httpx
from fastapi import HTTPException

from .config import (
    DEPENDENCY_TIMEOUT_SECONDS,
    DATABASE_UNAVAILABLE_MESSAGE,
    PRODUCT_SERVICE_URL,
    USER_SERVICE_URL,
)
from .models import OrderCreateRequest, OrderItemOut, OrderOut
from .repositories import OrderRepository


class OrderService:
    def __init__(
        self, repository: OrderRepository, logger: logging.Logger, storage: str
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._storage = storage

    def init_db(self) -> None:
        self._repository.init_db()

    def _ensure_user_exists(self, client: httpx.Client, user_id: int) -> None:
        response = client.get(
            f"{USER_SERVICE_URL}/users/{user_id}",
            timeout=DEPENDENCY_TIMEOUT_SECONDS,
        )
        if response.status_code == 404:
            self._logger.info("event=order_user_not_found user_id=%s", user_id)
            raise HTTPException(status_code=404, detail="user not found")
        if response.status_code >= 400:
            self._logger.warning(
                "event=order_user_service_unavailable user_id=%s status_code=%s",
                user_id,
                response.status_code,
            )
            raise HTTPException(status_code=502, detail="user-service unavailable")

    def _reserve_and_price_item(
        self, client: httpx.Client, product_id: int, quantity: int
    ) -> tuple[float, int, int]:
        product_response = client.get(
            f"{PRODUCT_SERVICE_URL}/products/{product_id}",
            timeout=DEPENDENCY_TIMEOUT_SECONDS,
        )
        if product_response.status_code == 404:
            self._logger.info("event=order_product_not_found product_id=%s", product_id)
            raise HTTPException(
                status_code=404, detail=f"product {product_id} not found"
            )
        if product_response.status_code >= 400:
            self._logger.warning(
                "event=order_product_service_unavailable product_id=%s status_code=%s",
                product_id,
                product_response.status_code,
            )
            raise HTTPException(status_code=502, detail="product-service unavailable")

        price = float(product_response.json()["price"])

        reserve_response = client.post(
            f"{PRODUCT_SERVICE_URL}/products/{product_id}/reserve",
            json={"quantity": quantity},
            timeout=DEPENDENCY_TIMEOUT_SECONDS,
        )
        if reserve_response.status_code == 409:
            self._logger.warning(
                "event=order_reserve_conflict product_id=%s quantity=%s",
                product_id,
                quantity,
            )
            raise HTTPException(
                status_code=409,
                detail=f"insufficient stock for product {product_id}",
            )
        if reserve_response.status_code >= 400:
            self._logger.warning(
                "event=order_reserve_failed product_id=%s quantity=%s status_code=%s",
                product_id,
                quantity,
                reserve_response.status_code,
            )
            raise HTTPException(status_code=502, detail="product reserve failed")

        reservation_payload = reserve_response.json()
        reservation_id = int(reservation_payload["reservation_id"])

        return price, quantity, reservation_id

    def _release_reserved_items(
        self, client: httpx.Client, reservation_ids: list[int]
    ) -> None:
        for reservation_id in reversed(reservation_ids):
            try:
                release_response = client.post(
                    f"{PRODUCT_SERVICE_URL}/reservations/{reservation_id}/cancel",
                    timeout=DEPENDENCY_TIMEOUT_SECONDS,
                )
                if release_response.status_code >= 400:
                    self._logger.error(
                        "event=order_cancel_failed reservation_id=%s status_code=%s",
                        reservation_id,
                        release_response.status_code,
                    )
            except Exception:
                self._logger.exception(
                    "event=order_cancel_error reservation_id=%s",
                    reservation_id,
                )

    def _confirm_reserved_items(
        self, client: httpx.Client, reservation_ids: list[int]
    ) -> None:
        for reservation_id in reservation_ids:
            confirm_response = client.post(
                f"{PRODUCT_SERVICE_URL}/reservations/{reservation_id}/confirm",
                timeout=DEPENDENCY_TIMEOUT_SECONDS,
            )
            if confirm_response.status_code >= 400:
                self._logger.error(
                    "event=order_confirm_failed reservation_id=%s status_code=%s",
                    reservation_id,
                    confirm_response.status_code,
                )
                raise HTTPException(status_code=502, detail="product confirm failed")

    def _mark_order_failed(self, order_id: int) -> None:
        try:
            updated = self._repository.update_order_status(order_id, "failed")
            if not updated:
                self._logger.error(
                    "event=order_mark_failed_missing order_id=%s storage=%s",
                    order_id,
                    self._storage,
                )
        except Exception:
            self._logger.exception(
                "event=order_mark_failed_error order_id=%s storage=%s",
                order_id,
                self._storage,
            )

    def create_order(self, payload: OrderCreateRequest) -> OrderOut:
        if not payload.items:
            self._logger.warning(
                "event=order_create_invalid reason=empty_items user_id=%s",
                payload.user_id,
            )
            raise HTTPException(status_code=400, detail="order items cannot be empty")

        with httpx.Client() as client:
            self._ensure_user_exists(client=client, user_id=payload.user_id)
            order_items: list[OrderItemOut] = []
            total_amount = 0.0
            reservation_ids: list[int] = []
            order_id: int | None = None

            try:
                for item in payload.items:
                    unit_price, quantity, reservation_id = self._reserve_and_price_item(
                        client=client,
                        product_id=item.product_id,
                        quantity=item.quantity,
                    )
                    reservation_ids.append(reservation_id)
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

                order = self._repository.create_order(
                    user_id=payload.user_id,
                    total_amount=total_amount,
                    order_items=order_items,
                    status="pending",
                )
                order_id = order.id
                self._confirm_reserved_items(
                    client=client, reservation_ids=reservation_ids
                )
                order = self._repository.update_order_status(order.id, "confirmed") or order
                self._logger.info(
                    "event=order_created order_id=%s user_id=%s items=%s total_amount=%.2f status=%s storage=%s",
                    order.id,
                    order.user_id,
                    len(order.items),
                    order.total_amount,
                    order.status,
                    self._storage,
                )
                return order
            except RuntimeError:
                self._release_reserved_items(client=client, reservation_ids=reservation_ids)
                self._logger.error(
                    "event=order_create_failed reason=persistence_empty user_id=%s storage=%s",
                    payload.user_id,
                    self._storage,
                )
                raise HTTPException(status_code=503, detail="order persistence failed")
            except HTTPException:
                if order_id is not None:
                    self._mark_order_failed(order_id)
                if reservation_ids:
                    self._release_reserved_items(
                        client=client, reservation_ids=reservation_ids
                    )
                raise
            except Exception as exc:
                if order_id is not None:
                    self._mark_order_failed(order_id)
                if reservation_ids:
                    self._release_reserved_items(
                        client=client, reservation_ids=reservation_ids
                    )
                self._logger.exception(
                    "event=order_create_error storage=%s user_id=%s",
                    self._storage,
                    payload.user_id,
                )
                raise HTTPException(
                    status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
                ) from exc

    def get_order(self, order_id: int) -> OrderOut:
        try:
            order = self._repository.get_order(order_id)
            if not order:
                self._logger.info(
                    "event=order_not_found order_id=%s storage=%s",
                    order_id,
                    self._storage,
                )
                raise HTTPException(status_code=404, detail="order not found")
            return order
        except HTTPException:
            raise
        except Exception as exc:
            self._logger.exception(
                "event=order_get_error order_id=%s storage=%s", order_id, self._storage
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def list_orders(self) -> list[OrderOut]:
        try:
            orders = self._repository.list_orders()
            self._logger.info(
                "event=order_list count=%s storage=%s", len(orders), self._storage
            )
            return orders
        except Exception as exc:
            self._logger.exception("event=order_list_error storage=%s", self._storage)
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc
