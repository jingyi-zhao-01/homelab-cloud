import logging

from fastapi import HTTPException

from .config import DATABASE_UNAVAILABLE_MESSAGE, PRODUCT_NOT_FOUND_MESSAGE
from .models import (
    ExpireReservationsResult,
    ProductCreate,
    ProductOut,
    ReservationOut,
    ReserveRequest,
)
from .repositories import ProductRepository


class ProductService:
    def __init__(
        self, repository: ProductRepository, logger: logging.Logger, storage: str
    ) -> None:
        self._repository = repository
        self._logger = logger
        self._storage = storage

    def startup(self) -> None:
        self._repository.init_db()
        self._repository.seed_if_empty()

    def create_product(self, payload: ProductCreate) -> ProductOut:
        try:
            product = self._repository.create_product(payload)
            self._logger.info(
                "event=product_created product_id=%s name=%s stock=%s storage=%s",
                product.id,
                product.name,
                product.stock,
                self._storage,
            )
            return product
        except RuntimeError:
            self._logger.error(
                "event=product_create_failed reason=persistence_empty name=%s storage=%s",
                payload.name,
                self._storage,
            )
            raise HTTPException(status_code=503, detail="product persistence failed")
        except HTTPException:
            raise
        except Exception as exc:
            self._logger.exception(
                "event=product_create_error storage=%s", self._storage
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def get_product(self, product_id: int) -> ProductOut:
        try:
            product = self._repository.get_product(product_id)
            if not product:
                self._logger.info(
                    "event=product_not_found product_id=%s storage=%s",
                    product_id,
                    self._storage,
                )
                raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MESSAGE)
            return product
        except HTTPException:
            raise
        except Exception as exc:
            self._logger.exception(
                "event=product_get_error storage=%s product_id=%s",
                self._storage,
                product_id,
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def reserve_product(
        self, product_id: int, payload: ReserveRequest
    ) -> ReservationOut:
        try:
            reservation = self._repository.reserve_product(product_id, payload.quantity)
            if not reservation:
                self._logger.info(
                    "event=product_not_found product_id=%s storage=%s",
                    product_id,
                    self._storage,
                )
                raise HTTPException(status_code=404, detail=PRODUCT_NOT_FOUND_MESSAGE)
            self._logger.info(
                "event=product_reserved product_id=%s quantity=%s storage=%s",
                product_id,
                payload.quantity,
                self._storage,
            )
            return reservation
        except ValueError as exc:
            self._logger.warning(
                "event=product_reserve_conflict product_id=%s quantity=%s storage=%s",
                product_id,
                payload.quantity,
                self._storage,
            )
            raise HTTPException(status_code=409, detail="insufficient stock") from exc
        except HTTPException:
            raise
        except Exception as exc:
            self._logger.exception(
                "event=product_reserve_error storage=%s product_id=%s quantity=%s",
                self._storage,
                product_id,
                payload.quantity,
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def confirm_reservation(self, reservation_id: int) -> ReservationOut:
        try:
            reservation = self._repository.confirm_reservation(reservation_id)
            if not reservation:
                self._logger.info(
                    "event=reservation_not_found reservation_id=%s storage=%s",
                    reservation_id,
                    self._storage,
                )
                raise HTTPException(status_code=404, detail="reservation not found")
            self._logger.info(
                "event=reservation_confirmed reservation_id=%s storage=%s",
                reservation_id,
                self._storage,
            )
            return reservation
        except HTTPException:
            raise
        except Exception as exc:
            self._logger.exception(
                "event=reservation_confirm_error storage=%s reservation_id=%s",
                self._storage,
                reservation_id,
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def cancel_reservation(self, reservation_id: int) -> ReservationOut:
        try:
            reservation = self._repository.cancel_reservation(reservation_id)
            if not reservation:
                self._logger.info(
                    "event=reservation_not_found reservation_id=%s storage=%s",
                    reservation_id,
                    self._storage,
                )
                raise HTTPException(status_code=404, detail="reservation not found")
            self._logger.info(
                "event=reservation_cancelled reservation_id=%s storage=%s",
                reservation_id,
                self._storage,
            )
            return reservation
        except HTTPException:
            raise
        except Exception as exc:
            self._logger.exception(
                "event=reservation_cancel_error storage=%s reservation_id=%s",
                self._storage,
                reservation_id,
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def expire_reservations(self) -> ExpireReservationsResult:
        try:
            expired_count = self._repository.expire_reservations()
            self._logger.info(
                "event=reservation_expired expired_count=%s storage=%s",
                expired_count,
                self._storage,
            )
            return ExpireReservationsResult(expired_count=expired_count)
        except Exception as exc:
            self._logger.exception(
                "event=reservation_expire_error storage=%s",
                self._storage,
            )
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc

    def list_products(self) -> list[ProductOut]:
        try:
            products = self._repository.list_products()
            self._logger.info(
                "event=product_list count=%s storage=%s", len(products), self._storage
            )
            return products
        except Exception as exc:
            self._logger.exception("event=product_list_error storage=%s", self._storage)
            raise HTTPException(
                status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE
            ) from exc
