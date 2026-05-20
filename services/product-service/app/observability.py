import logging
import os
import time
from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response


def configure_service_logger(service_name: str) -> logging.Logger:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    return logging.getLogger(service_name)


def create_request_logging_middleware(
    logger: logging.Logger, service_name: str
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        request_id = request.headers.get("x-request-id", str(uuid4()))
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        log_fn = logger.error if response.status_code >= 400 else logger.info
        log_fn(
            "event=request service=%s request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
            service_name,
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["x-request-id"] = request_id
        return response

    return middleware
