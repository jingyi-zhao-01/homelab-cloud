import logging

from fastapi import HTTPException

from .config import DATABASE_UNAVAILABLE_MESSAGE, PRODUCT_NOT_FOUND_MESSAGE
from .models import ProductCreate, ProductOut, ReserveRequest
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

    def reserve_product(self, product_id: int, payload: ReserveRequest) -> ProductOut:
        try:
            updated = self._repository.reserve_product(product_id, payload.quantity)
            if not updated:
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
            return updated
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
