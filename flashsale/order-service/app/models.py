from typing import Literal

from pydantic import BaseModel, Field

OrderStatus = Literal["pending", "confirmed", "failed"]


class OrderItemRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreateRequest(BaseModel):
    user_id: int
    items: list[OrderItemRequest]


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
    items: list[OrderItemOut]
