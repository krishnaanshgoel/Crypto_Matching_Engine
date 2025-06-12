from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field

from engine.base_models import Order, OrderSide, OrderType

class Trade(BaseModel):
    id: str
    symbol: str
    price: Decimal
    quantity: Decimal
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    buy_order_id: Optional[str] = None
    sell_order_id: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            Decimal: lambda d: str(d)
        }

class BBO(BaseModel):
    symbol: str
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    best_bid_quantity: Optional[Decimal] = None
    best_ask_quantity: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            Decimal: lambda d: str(d)
        }
