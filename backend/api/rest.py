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


from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from decimal import Decimal
from datetime import datetime

from engine.base_models import Order, OrderSide
from engine.matching_engine import get_or_create_engine
from schemas import OrderRequest
from fastapi.responses import JSONResponse

router = APIRouter()

# NOTE: Set symbol explicitly (you can also refactor to support multiple symbols)
order_book = OrderBook(symbol="BTC-USDT")

@router.post("/submit")
async def submit_order(order_data: OrderRequest):
    order_dict = order_data.dict()
    order = Order.create(order_dict)
    engine = get_or_create_engine()
    trades = await engine.process_order(order)

    return {
        "order_id": order.id,
        "status": order.status,
        "filled_quantity": order.filled_quantity,
        "trades": [t.to_dict() for t in trades]
    }

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
