import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4
from decimal import Decimal
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
# from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade
from engine.matching_engine import MatchingEngine
from engine.order_book import OrderBook
from api.schemas import OrderRequest, OrderResponse, MarketDataResponse, TradeResponse
from api.rest import router as rest_router

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files and templates
# static_dir = os.path.join(os.path.dirname(__file__), "static")
# if os.path.isdir(static_dir):
#     app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if os.path.isdir(templates_dir):
    templates = Jinja2Templates(directory=templates_dir)
else:
    templates = None

# Include the REST API router
app.include_router(rest_router, prefix="/api")

# Global matching engine instance
matching_engine: Optional[MatchingEngine] = None

def get_or_create_engine() -> MatchingEngine:
    global matching_engine
    if matching_engine is None:
        matching_engine = MatchingEngine()
    return matching_engine

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serve the main trading interface."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/orders")
async def create_order(order_data: dict):
    try:
        # Validate required fields
        required_fields = ["symbol", "side", "order_type", "quantity"]
        for field in required_fields:
            if field not in order_data:
                raise HTTPException(status_code=422, detail=f"Missing required field: {field}")

        # Convert and validate side
        try:
            side = OrderSide[order_data["side"]]
        except KeyError:
            raise HTTPException(status_code=422, detail="Invalid side")

        # Convert and validate order type
        try:
            order_type = OrderType[order_data["order_type"]]
        except KeyError:
            raise HTTPException(status_code=422, detail="Invalid order type")

        # Convert and validate quantity
        try:
            quantity = Decimal(str(order_data["quantity"]))
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Invalid quantity")

        # Convert and validate price for limit and stop-limit orders
        price = None
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT]:
            if "price" not in order_data:
                raise HTTPException(status_code=422, detail="Price required for limit and stop-limit orders")
            try:
                price = Decimal(str(order_data["price"]))
                if price <= 0:
                    raise ValueError("Price must be positive")
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="Invalid price")

        # Convert and validate stop price for stop orders
        stop_price = None
        if order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT]:
            if "stop_price" not in order_data:
                raise HTTPException(status_code=422, detail="Stop price required for stop orders")
            try:
                stop_price = Decimal(str(order_data["stop_price"]))
                if stop_price <= 0:
                    raise ValueError("Stop price must be positive")
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="Invalid stop price")

        # Create order
        order = Order(
            symbol=order_data["symbol"],
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price
        )

        # Process order
        engine = get_or_create_engine()
        trades = await engine.process_order(order)

        # Return response
        response = {
            "symbol": order.symbol,
            "order_id": order.id,
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

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/orders/{order_id}")
async def cancel_order(order_id: str):
    engine = get_or_create_engine()
    success = engine.cancel_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": "cancelled"}

@app.get("/market-data/{symbol}")
async def get_market_data(symbol: str):
    """Get current market data for a symbol."""
    engine = get_or_create_engine()
    bbo = engine.get_bbo(symbol)
    
    return bbo

@app.get("/pending-orders/{symbol}")
async def get_pending_orders(symbol: str):
    """Get all pending orders for a given symbol."""
    engine = get_or_create_engine()
    order_book = engine.get_order_book(symbol)
    pending_orders = order_book.get_pending_orders()
    
    return {
        "symbol": symbol,
        "timestamp": datetime.utcnow().isoformat(),
        "bids": pending_orders["bids"],
        "asks": pending_orders["asks"]
    }

async def market_data_callback(symbol: str, message: str):
    safe_symbol = symbol.replace('/', '_')
    if safe_symbol in market_data_clients:
        for client in list(market_data_clients[safe_symbol]):
            try:
                await client.send_text(message)
            except:
                market_data_clients[safe_symbol].remove(client)

async def trade_callback(symbol: str, message: str):
    safe_symbol = symbol.replace('/', '_')
    if safe_symbol in trade_clients:
        for client in list(trade_clients[safe_symbol]):
            try:
                await client.send_text(message)
            except:
                trade_clients[safe_symbol].remove(client)

async def order_callback(symbol: str, message: str):
    safe_symbol = symbol.replace('/', '_')
    if safe_symbol in order_clients:
        for client in list(order_clients[safe_symbol]):
            try:
                await client.send_text(message)
            except:
                order_clients[safe_symbol].remove(client)

# WebSocket endpoints
@app.websocket("/ws/market/{symbol}")
async def websocket_market_endpoint(websocket: WebSocket, symbol: str):
    engine = get_or_create_engine()
    try:
        await websocket.accept()
        queue = engine.subscribe("market_data")
        
        while True:
            data = await queue.get()
            await websocket.send_json(data)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1000, reason=str(e))

@app.websocket("/ws/trades/{symbol}")
async def websocket_trades_endpoint(websocket: WebSocket, symbol: str):
    engine = get_or_create_engine()
    try:
        await websocket.accept()
        queue = engine.subscribe("trades")
        
        while True:
            data = await queue.get()
            await websocket.send_json(data)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1000, reason=str(e))

@app.websocket("/ws/orders/{symbol}")
async def websocket_orders_endpoint(websocket: WebSocket, symbol: str):
    engine = get_or_create_engine()
    try:
        await websocket.accept()
        queue = engine.subscribe("orders")
        
        while True:
            data = await queue.get()
            await websocket.send_json(data)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1000, reason=str(e))
