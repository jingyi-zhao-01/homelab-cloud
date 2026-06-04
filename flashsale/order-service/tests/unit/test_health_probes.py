import sys
import types
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

psycopg_stub = types.ModuleType("psycopg")
psycopg_rows_stub = types.ModuleType("psycopg.rows")
psycopg_stub.connect = None
psycopg_rows_stub.dict_row = object()
sys.modules.setdefault("psycopg", psycopg_stub)
sys.modules.setdefault("psycopg.rows", psycopg_rows_stub)

from app.main import app


class OrderServiceHealthProbeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_live_ignores_repository_health(self) -> None:
        with patch("app.main.repository.is_healthy", side_effect=RuntimeError("db down")):
            response = self.client.get("/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_health_returns_503_when_database_check_fails(self) -> None:
        with patch("app.main.repository.is_healthy", side_effect=RuntimeError("db down")):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "database-unavailable")


if __name__ == "__main__":
    unittest.main()
