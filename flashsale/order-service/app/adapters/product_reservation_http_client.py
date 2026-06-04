from collections.abc import Callable

from fastapi import HTTPException

from app.config import DEPENDENCY_TIMEOUT_SECONDS, PRODUCT_SERVICE_URL
from app.domain.statuses import TerminalizationAction


class ProductReservationHttpClient:
    def __init__(self, client_factory: Callable[[], object]) -> None:
        self._client_factory = client_factory

    def reserve(self, product_id: int, quantity: int) -> tuple[float, int, int]:
        with self._client_factory() as client:
            response = client.post(
                f"{PRODUCT_SERVICE_URL}/products/{product_id}/reserve",
                json={"quantity": quantity},
                timeout=DEPENDENCY_TIMEOUT_SECONDS,
            )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail=f"product {product_id} not found")
        if response.status_code == 409:
            raise HTTPException(
                status_code=409,
                detail=f"insufficient stock for product {product_id}",
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="product reserve failed")
        payload = response.json()
        if payload.get("unit_price") is None:
            raise HTTPException(status_code=502, detail="product reserve missing price")
        return (
            float(payload["unit_price"]),
            int(quantity),
            int(payload["reservation_id"]),
        )

    def release(self, reservation_ids: list[int]) -> None:
        with self._client_factory() as client:
            for reservation_id in reversed(reservation_ids):
                try:
                    client.post(
                        f"{PRODUCT_SERVICE_URL}/reservations/{reservation_id}/cancel",
                        timeout=DEPENDENCY_TIMEOUT_SECONDS,
                    )
                except Exception:
                    continue

    def terminalize(
        self,
        reservation_id: int,
        action: TerminalizationAction,
    ) -> tuple[bool, str | None]:
        try:
            with self._client_factory() as client:
                response = client.post(
                    f"{PRODUCT_SERVICE_URL}/reservations/{reservation_id}/{action}",
                    timeout=DEPENDENCY_TIMEOUT_SECONDS,
                )
            if response.status_code >= 400:
                return False, f"status_code={response.status_code}"
            return True, None
        except Exception as exc:
            return False, exc.__class__.__name__
