from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4
from pydantic import BaseModel, Field

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    STOP_LOSS = "STOP_LOSS"
    STOP_LIMIT = "STOP_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: Decimal
    price: Optional[Decimal] = None
    stop_price: Optional[Decimal] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    filled_quantity: Decimal = Decimal('0')
    status: str = "NEW"
    triggered: bool = False

    def dict(self, *args, **kwargs):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "stop_price": str(self.stop_price) if self.stop_price else None,
            "timestamp": self.timestamp.isoformat(),
            "filled_quantity": str(self.filled_quantity),
            "status": self.status,
            "triggered": self.triggered
        }

class Trade(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    symbol: str
    price: Decimal
    quantity: Decimal
    side: OrderSide
    buy_order_id: str
    sell_order_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def dict(self, *args, **kwargs):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "side": self.side,
            "buy_order_id": self.buy_order_id,
            "sell_order_id": self.sell_order_id,
            "timestamp": self.timestamp.isoformat()
        } 