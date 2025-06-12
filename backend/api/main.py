import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4
from decimal import Decimal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade
from engine.matching_engine import MatchingEngine
from engine.order_book import OrderBook
from api.schemas import OrderRequest, OrderResponse, MarketDataResponse, TradeResponse

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
# app.mount("/static", StaticFiles(directory="api/static"), name="static")
templates = Jinja2Templates(directory="api/templates")

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
        engine = get_or_create_engine()
        
        # Validate required fields
        required_fields = ['symbol', 'side', 'order_type', 'quantity']
        for field in required_fields:
            if field not in order_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Convert and validate side
        try:
            side = OrderSide(order_data['side'].upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid side: {order_data['side']}. Must be 'BUY' or 'SELL'")
        
        # Convert and validate order type
        try:
            order_type = OrderType(order_data['order_type'].upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid order type: {order_data['order_type']}. Must be 'MARKET', 'LIMIT', 'IOC', or 'FOK'")
        
        # Convert and validate quantity
        try:
            quantity = Decimal(str(order_data['quantity']))
            if quantity <= 0:
                raise ValueError("Quantity must be positive")
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Invalid quantity. Must be a positive number")
        
        # Convert and validate price for limit orders
        price = None
        if order_type != OrderType.MARKET:
            if 'price' not in order_data:
                raise HTTPException(status_code=400, detail="Price is required for non-market orders")
            try:
                price = Decimal(str(order_data['price']))
                if price <= 0:
                    raise ValueError("Price must be positive")
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Invalid price. Must be a positive number")
        
        # Create order
        order = Order(
            symbol=order_data['symbol'],
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            order_id=str(uuid4())
        )
        
        # Process order
        trades = await engine.process_order(order)
        
        return {
            "order": order.dict(),
            "trades": [trade.dict() for trade in trades]
        }
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

@app.websocket("/ws/market/{symbol}")
async def websocket_market_endpoint(websocket: WebSocket, symbol: str):
    engine = get_or_create_engine()
    try:
        await engine.subscribe_market_data(websocket, symbol)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.unsubscribe_market_data(websocket, symbol)

@app.websocket("/ws/trades/{symbol}")
async def websocket_trades_endpoint(websocket: WebSocket, symbol: str):
    engine = get_or_create_engine()
    try:
        await engine.subscribe_trades(websocket, symbol)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.unsubscribe_trades(websocket, symbol)

@app.websocket("/ws/orders/{symbol}")
async def websocket_orders_endpoint(websocket: WebSocket, symbol: str):
    engine = get_or_create_engine()
    try:
        await engine.subscribe_orders(websocket, symbol)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        engine.unsubscribe_orders(websocket, symbol)
