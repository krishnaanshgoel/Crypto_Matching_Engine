# from fastapi import APIRouter
# from engine.order import Order
# from engine.order_book import OrderBook

# router = APIRouter()
# order_book = OrderBook()

# @router.post("/submit")
# def submit_order(order_data: dict):
#     order = Order.create(order_data)
#     fills = order_book.add_order(order)
#     return {
#         "order_id": order.id,
#         "fills": [f.to_dict() for f in fills]
#     }


from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Optional
from decimal import Decimal
from datetime import datetime
import uuid

from engine.base_models import Order, OrderSide, OrderType
from engine.matching_engine import get_or_create_engine, MatchingEngine, OrderBook
from engine.models import Trade
from schemas.order import OrderRequest
from fastapi.responses import JSONResponse

router = APIRouter()

# Initialize matching engine
matching_engine = MatchingEngine()

# Initialize order book for BTC-USDT
order_book = get_or_create_engine("BTC-USDT")

@router.post("/orders")
async def create_order(order_request: OrderRequest):
    """Create a new order."""
    try:
        # Convert request to Order object
        order = Order(
            id=order_request.id,
            symbol=order_request.symbol,
            side=OrderSide[order_request.side],
            order_type=OrderType[order_request.order_type],
            quantity=Decimal(str(order_request.quantity)),
            price=Decimal(str(order_request.price)) if order_request.price else None,
            timestamp=datetime.utcnow()
        )
        
        # Add order to matching engine
        trades = order_book.add_order(order)
        
        return {
            "order_id": order.id,
            "status": "FILLED" if not order.quantity else "PARTIALLY_FILLED",
            "trades": [trade.dict() for trade in trades]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/pending-orders/{symbol}")
async def get_pending_orders(symbol: str):
    """Get pending orders for a symbol."""
    try:
        # Get the order book for the symbol
        book = get_or_create_engine(symbol)
        
        # Get bids and asks
        bids = []
        for price, orders in book.bids.items():
            for order in orders:
                bids.append({
                    "id": order.id,
                    "price": float(price),
                    "quantity": float(order.quantity),
                    "timestamp": order.timestamp.isoformat()
                })
        
        asks = []
        for price, orders in book.asks.items():
            for order in orders:
                asks.append({
                    "id": order.id,
                    "price": float(price),
                    "quantity": float(order.quantity),
                    "timestamp": order.timestamp.isoformat()
                })
        
        return {
            "symbol": symbol,
            "bids": sorted(bids, key=lambda x: x["price"], reverse=True),
            "asks": sorted(asks, key=lambda x: x["price"])
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/trades/{symbol}")
async def get_recent_trades(symbol: str, limit: int = 100):
    """Get recent trades for a symbol."""
    try:
        # Get the order book for the symbol
        book = get_or_create_engine(symbol)
        
        # Get recent trades
        trades = book.trades[-limit:]
        
        return {
            "symbol": symbol,
            "trades": [trade.dict() for trade in trades]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/market-data/{symbol}/depth")
async def get_order_book_depth(symbol: str, depth: Optional[int] = 10) -> Dict:
    """Get top N levels of the order book for a symbol.
    
    Args:
        symbol: Trading pair symbol (e.g., "BTC-USD")
        depth: Number of price levels to return (default: 10)
        
    Returns:
        Dictionary containing order book depth data
    """
    if depth < 1 or depth > 100:
        raise HTTPException(status_code=400, detail="Depth must be between 1 and 100")
        
    engine = get_or_create_engine(symbol)
    order_book = engine.order_book
    
    depth_data = order_book.get_top_levels(depth)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "bids": depth_data["bids"],
        "asks": depth_data["asks"]
    }
