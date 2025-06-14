from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from uuid import uuid4
from engine.base_models import OrderSide, OrderType

class OrderRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    order_type: str  # "MARKET", "LIMIT", "IOC", "FOK", "STOP_LOSS", "STOP_LIMIT", "TAKE_PROFIT"
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None

    class Config:
        json_encoders = {
            Decimal: str
        } 