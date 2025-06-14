
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from typing import Dict, Set, List, Optional
import json
import asyncio
from datetime import datetime
from engine.globals import matching_engine
import logging
from decimal import Decimal
from uuid import uuid4

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade
from engine.websocket_manager import WebSocketManager

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

# Create WebSocket manager instance
ws_manager = WebSocketManager()

# Store active connections
active_connections: Dict[str, List[WebSocket]] = {
    "market_data": [],
    "trades": [],
    "orders": []
}

# Store order update queues for each symbol
order_queues: Dict[str, asyncio.Queue] = {}

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol format to ensure consistency."""
    return symbol.upper().replace('-', '_')

async def broadcast_market_data(symbol: str):
    """Broadcast market data to all connected clients"""
    normalized_symbol = normalize_symbol(symbol)
    while True:
        try:
            order_book = matching_engine.get_order_book(normalized_symbol)
            
            # Get market data including BBO and depth
            bbo = order_book.get_bbo()
            depth_data = order_book.get_top_levels(10)  # Get top 10 levels
            
            market_data = {
                "type": "market_data",
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "bbo": bbo,
                "bids": depth_data["bids"],
                "asks": depth_data["asks"]
            }
            
            # Broadcast to all connected clients
            disconnected = set()
            for connection in active_connections["market_data"]:
                try:
                    await connection.send_json(market_data)
                except WebSocketDisconnect:
                    disconnected.add(connection)
                except Exception as e:
                    print(f"Error sending market data: {e}")
                    disconnected.add(connection)
            
            # Remove disconnected clients
            for connection in disconnected:
                active_connections["market_data"].remove(connection)
            
            await asyncio.sleep(1)  # Update every second
        except Exception as e:
            print(f"Error in market data broadcast: {e}")
            await asyncio.sleep(1)

@router.websocket("/ws/market-data/{symbol}")
async def market_data_websocket(websocket: WebSocket, symbol: str):
    client_id = str(uuid4())
    try:
        await ws_manager.connect(websocket, client_id, f"market_data_{symbol}")
        
        # Send initial market data
        order_book = matching_engine.get_order_book(symbol)
        bbo=matching_engine.get_bbo(symbol)
        await ws_manager.broadcast_market_data(
            f"market_data_{symbol}",
            order_book.get_pending_orders(),
            bbo
        )
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in market data websocket: {e}")
                break
    finally:
        await ws_manager.disconnect(client_id, f"market_data_{symbol}")

@router.websocket("/ws/trades/{symbol}")
async def trades_websocket(websocket: WebSocket, symbol: str):
    client_id = str(uuid4())
    try:
        await ws_manager.connect(websocket, client_id, f"trades_{symbol}")
        
        # Send recent trades
        if matching_engine.redis:
            recent_trades = await matching_engine.redis.get_recent_trades(symbol)
            for trade in recent_trades:
                await ws_manager.broadcast_trade(f"trades_{symbol}", trade.dict())
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in trades websocket: {e}")
                break
    finally:
        await ws_manager.disconnect(client_id, f"trades_{symbol}")

@router.websocket("/ws/orders/{symbol}")
async def orders_websocket(websocket: WebSocket, symbol: str):
    client_id = str(uuid4())
    try:
        await ws_manager.connect(websocket, client_id, f"orders_{symbol}")
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in orders websocket: {e}")
                break
    finally:
        await ws_manager.disconnect(client_id, f"orders_{symbol}")

@router.websocket("/ws/pending-orders/{symbol}")
async def pending_orders_websocket(websocket: WebSocket, symbol: str):
    client_id = str(uuid4())
    try:
        await ws_manager.connect(websocket, client_id, f"pending_orders_{symbol}")
        
        # Send initial pending orders
        order_book = matching_engine.get_order_book(symbol)
        bbo = matching_engine.get_bbo(symbol)
        
        # Format pending orders
        pending_orders = {
            'bids': [
                {
                    'price': str(level.price),
                    'quantity': str(level.total_quantity),
                    'orders': [
                        {
                            'id': order.id,
                            'side': order.side.value,
                            'type': order.order_type.value,
                            'quantity': str(order.quantity),
                            'filled_quantity': str(order.filled_quantity),
                            'status': order.status,
                            'timestamp': order.timestamp.isoformat() if hasattr(order, 'timestamp') else datetime.utcnow().isoformat()
                        }
                        for order in level.orders
                    ]
                }
                for level in sorted(order_book.bids.values(), reverse=True)
            ],
            'asks': [
                {
                    'price': str(level.price),
                    'quantity': str(level.total_quantity),
                    'orders': [
                        {
                            'id': order.id,
                            'side': order.side.value,
                            'type': order.order_type.value,
                            'quantity': str(order.quantity),
                            'filled_quantity': str(order.filled_quantity),
                            'status': order.status,
                            'timestamp': order.timestamp.isoformat() if hasattr(order, 'timestamp') else datetime.utcnow().isoformat()
                        }
                        for order in level.orders
                    ]
                }
                for level in sorted(order_book.asks.values())
            ],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Sending initial pending orders for {symbol}")
        logger.info(f"Bids: {len(pending_orders['bids'])}, Asks: {len(pending_orders['asks'])}")
        await ws_manager.broadcast_order(f"pending_orders_{symbol}", pending_orders, bbo)
        
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any client messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in pending orders websocket: {e}")
                break
    finally:
        await ws_manager.disconnect(client_id, f"pending_orders_{symbol}")

# Update matching engine broadcast methods to use WebSocket manager
async def broadcast_market_data(symbol: str, data: dict, bbo: dict):
    await ws_manager.broadcast_market_data(f"market_data_{symbol}", data, bbo)

async def broadcast_trade(symbol: str, trade: dict):
    await ws_manager.broadcast_trade(f"trades_{symbol}", trade)

async def broadcast_order(symbol: str, order: dict, data: dict):
    await ws_manager.broadcast_order(f"orders_{symbol}", order, data)
    await ws_manager.broadcast_order(f"pending_orders_{symbol}", order, data)

@router.websocket("/ws/test")
async def test_socket(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_text("Hello from server")
        await asyncio.sleep(1)
