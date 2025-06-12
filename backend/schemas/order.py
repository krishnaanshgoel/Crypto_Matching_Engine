from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from uuid import uuid4

class OrderRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", "IOC", "FOK"
    quantity: Decimal
    price: Optional[Decimal] = None

    class Config:
        json_encoders = {
            Decimal: str
        } 