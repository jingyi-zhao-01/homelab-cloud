from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal["pending", "confirmed", "failed", "cancelled", "expired"]
PaymentStatus = Literal["pending", "succeeded", "cancelled"]
PaymentWebhookStatus = Literal["succeeded"]


class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreateRequest(BaseModel):
    user_id: int
    items: list[OrderItemRequest]
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class OrderItemOut(BaseModel):
    product_id: int
    quantity: int
    unit_price: float
    line_total: float


class OrderOut(BaseModel):
    id: int
    user_id: int
    created_at: str
    total_amount: float
    status: OrderStatus
    payment_status: PaymentStatus
    idempotency_key: str | None = None
    items: list[OrderItemOut]


class ExpireOrdersResult(BaseModel):
    expired_count: int


class PaymentWebhookRequest(BaseModel):
    order_id: int
    event_id: str | None = Field(default=None, min_length=1, max_length=128)
    status: PaymentWebhookStatus = "succeeded"
