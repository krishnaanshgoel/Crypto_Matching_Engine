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
from uuid import uuid4

from engine.base_models import Order, OrderSide, OrderType
from engine.globals import matching_engine
from engine.models import Trade
from schemas.order import OrderRequest
from fastapi.responses import JSONResponse
from engine.order_book import OrderBook

router = APIRouter()

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol format to ensure consistency."""
    return symbol.upper().replace('-', '_')

@router.get("/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get current market data for a symbol."""
    try:
        normalized_symbol = normalize_symbol(symbol)
        order_book = matching_engine.get_order_book(normalized_symbol)
        bbo = order_book.get_bbo()
        depth = order_book.get_top_levels(10)
        
        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "bbo": bbo,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/pending-orders/{symbol}")
async def get_pending_orders(symbol: str):
    """Get pending orders for a symbol."""
    try:
        normalized_symbol = normalize_symbol(symbol)
        order_book = matching_engine.get_order_book(normalized_symbol)
        pending_orders = order_book.get_pending_orders()
        
        return {
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "bids": pending_orders["bids"],
            "asks": pending_orders["asks"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/orders")
async def create_order(order_request: OrderRequest):
    """Create a new order."""
    try:
        # Normalize symbol
        normalized_symbol = normalize_symbol(order_request.symbol)
        
        # Convert request to Order object
        order = Order(
            id=str(uuid4()),
            symbol=normalized_symbol,
            side=OrderSide[order_request.side],
            order_type=OrderType[order_request.order_type],
            quantity=Decimal(str(order_request.quantity)),
            price=Decimal(str(order_request.price)) if order_request.price else None,
            stop_price=Decimal(str(order_request.stop_price)) if order_request.stop_price else None,
            timestamp=datetime.utcnow()
        )
        
        # Process the order using the matching engine
        trades = await matching_engine.process_order(order)
        
        # Prepare response
        response = {
            "order_id": order.id,
            "symbol": order_request.symbol,  # Return original symbol format
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "status": order.status,
            "trades": [trade.dict() for trade in trades]
        }
        
        # Add optional fields if present
        if order.price is not None:
            response["price"] = str(order.price)
        if order.stop_price is not None:
            response["stop_price"] = str(order.stop_price)
            
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/trades/{symbol}")
async def get_recent_trades(symbol: str, limit: int = 100):
    """Get recent trades for a symbol."""
    try:
        normalized_symbol = normalize_symbol(symbol)
        order_book = matching_engine.get_order_book(normalized_symbol)
        
        # Get recent trades
        trades = order_book.trades[-limit:]
        
        return {
            "symbol": symbol,
            "trades": [trade.dict() for trade in trades]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/market-data/{symbol}/depth")
async def get_order_book_depth(symbol: str, depth: Optional[int] = 10) -> Dict:
    """Get top N levels of the order book for a symbol."""
    if depth < 1 or depth > 100:
        raise HTTPException(status_code=400, detail="Depth must be between 1 and 100")
        
    normalized_symbol = normalize_symbol(symbol)
    order_book = matching_engine.get_order_book(normalized_symbol)
    
    depth_data = order_book.get_top_levels(depth)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "bids": depth_data["bids"],
        "asks": depth_data["asks"]
    }
