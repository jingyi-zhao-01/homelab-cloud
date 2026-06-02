import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / "flashsale" / "scripts"))

from integration_test_support import (
    FlashsaleIntegrationClient,
    reset_services,
    wait_for_stack,
)


class ProductServiceComposeIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        wait_for_stack()

    def setUp(self) -> None:
        reset_services()
        self.client = FlashsaleIntegrationClient()
        self.user_id = self.client.create_user()
        self.product_id = self.client.create_product(
            name="Compose Product",
            price=19.99,
            stock=5,
        )

    def test_order_consumes_stock(self) -> None:
        self.client.create_order(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=2,
            idempotency_key="compose-order-stock",
        )

        product = self.client.get_product(self.product_id)
        self.assertEqual(str(product["stock"]), "3")

    def test_duplicate_order_replay_does_not_change_stock(self) -> None:
        first = self.client.create_order(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=2,
            idempotency_key="compose-order-dup",
        )
        replay = self.client.create_order(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=2,
            idempotency_key="compose-order-dup",
        )

        product = self.client.get_product(self.product_id)
        self.assertEqual(int(replay["id"]), int(first["id"]))
        self.assertEqual(str(product["stock"]), "3")

    def test_out_of_stock_order_returns_conflict(self) -> None:
        self.client.create_order(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=2,
            idempotency_key="compose-order-base",
        )
        conflict = self.client.create_order(
            user_id=self.user_id,
            product_id=self.product_id,
            quantity=4,
            idempotency_key="compose-order-oos",
            expected_status=409,
        )

        product = self.client.get_product(self.product_id)
        self.assertIn("detail", conflict)
        self.assertEqual(str(product["stock"]), "3")


if __name__ == "__main__":
    unittest.main()
