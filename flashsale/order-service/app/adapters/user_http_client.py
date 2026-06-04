from collections.abc import Callable

from fastapi import HTTPException
from opentelemetry.trace import SpanKind

from app.config import USER_SERVICE_TIMEOUT_SECONDS, USER_SERVICE_URL
from app.observability import inject_trace_headers, start_span


class UserHttpClient:
    def __init__(self, client_factory: Callable[[], object]) -> None:
        self._client_factory = client_factory

    def ensure_user_exists(self, user_id: int) -> None:
        with start_span(
            "order-service",
            "user-service lookup",
            kind=SpanKind.CLIENT,
            attributes={
                "http.request.method": "GET",
                "server.address": USER_SERVICE_URL,
                "flashsale.user_id": user_id,
            },
        ):
            with self._client_factory() as client:
                response = client.get(
                    f"{USER_SERVICE_URL}/users/{user_id}",
                    headers=inject_trace_headers(),
                    timeout=USER_SERVICE_TIMEOUT_SECONDS,
                )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="user not found")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="user-service unavailable")
