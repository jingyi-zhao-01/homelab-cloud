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
