from typing import Literal

from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    name: str
    price: float = Field(gt=0)
    stock: int = Field(ge=0)


class ProductOut(BaseModel):
    id: int
    name: str
    price: float
    stock: int


class ReserveRequest(BaseModel):
    quantity: int = Field(gt=0)


ReservationStatus = Literal["reserved", "confirmed", "cancelled", "expired"]


class ReservationOut(BaseModel):
    reservation_id: int
    product_id: int
    quantity: int
    status: ReservationStatus
    expires_at: str | None = None


class ExpireReservationsResult(BaseModel):
    expired_count: int
