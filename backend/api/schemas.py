
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

# Import Enums from your engine
from engine.models import OrderSide, OrderType

class OrderRequest(BaseModel):
    symbol: str
    side: OrderSide  # was str; now uses Enum
    type: OrderType  # was str; now uses Enum
    quantity: float
    price: Optional[float] = None


class TradeResponse(BaseModel):
    id: str
    price: float
    quantity: float
    timestamp: datetime


class OrderResponse(BaseModel):
    order_id: str
    status: str
    filled_quantity: float
    trades: List[TradeResponse]


class MarketDataResponse(BaseModel):
    symbol: str
    best_bid: Optional[float]
    best_ask: Optional[float]
    best_bid_quantity: float
    best_ask_quantity: float
    timestamp: datetime
