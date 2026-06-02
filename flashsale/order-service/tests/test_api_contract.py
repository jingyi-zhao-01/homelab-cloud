import sys
import types
import unittest

psycopg_stub = types.ModuleType("psycopg")
psycopg_rows_stub = types.ModuleType("psycopg.rows")
psycopg_stub.connect = None
psycopg_rows_stub.dict_row = object()
sys.modules.setdefault("psycopg", psycopg_stub)
sys.modules.setdefault("psycopg.rows", psycopg_rows_stub)

from app.main import app


class OrderServiceApiContractTest(unittest.TestCase):
    def test_openapi_exposes_order_and_payment_endpoints(self) -> None:
        spec = app.openapi()

        self.assertIn("/orders", spec["paths"])
        self.assertIn("/payments/webhook", spec["paths"])
        self.assertIn("/admin/expire-orders", spec["paths"])

        webhook_post = spec["paths"]["/payments/webhook"]["post"]
        request_schema = webhook_post["requestBody"]["content"]["application/json"][
            "schema"
        ]
        self.assertEqual(
            request_schema["$ref"], "#/components/schemas/PaymentWebhookRequest"
        )

    def test_order_schemas_include_idempotency_and_payment_fields(self) -> None:
        spec = app.openapi()
        create_schema = spec["components"]["schemas"]["OrderCreateRequest"]
        order_schema = spec["components"]["schemas"]["OrderOut"]

        self.assertIn("idempotency_key", create_schema["properties"])
        self.assertIn("status", order_schema["properties"])
        self.assertIn("payment_status", order_schema["properties"])
        self.assertIn("idempotency_key", order_schema["properties"])


if __name__ == "__main__":
    unittest.main()
