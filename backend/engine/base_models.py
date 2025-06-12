from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    IOC = "IOC"
    FOK = "FOK"

class Order:
    def __init__(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        order_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.id = order_id or str(uuid4())
        self.symbol = symbol
        self.side = side
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.timestamp = timestamp or datetime.utcnow()
        self.filled_quantity = Decimal('0')
        self.status = "NEW"

    def dict(self):
        return {
            "id": self.id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": str(self.quantity),
            "price": str(self.price) if self.price else None,
            "timestamp": self.timestamp.isoformat(),
            "filled_quantity": str(self.filled_quantity),
            "status": self.status
        } 