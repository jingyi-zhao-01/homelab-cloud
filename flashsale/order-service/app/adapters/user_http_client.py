from collections.abc import Callable

from fastapi import HTTPException

from app.config import DEPENDENCY_TIMEOUT_SECONDS, USER_SERVICE_URL


class UserHttpClient:
    def __init__(self, client_factory: Callable[[], object]) -> None:
        self._client_factory = client_factory

    def ensure_user_exists(self, user_id: int) -> None:
        with self._client_factory() as client:
            response = client.get(
                f"{USER_SERVICE_URL}/users/{user_id}",
                timeout=DEPENDENCY_TIMEOUT_SECONDS,
            )
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="user not found")
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail="user-service unavailable")
