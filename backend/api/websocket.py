# from fastapi import WebSocket, APIRouter
# from engine.order_book import OrderBook
# import asyncio
# import json

# router = APIRouter()
# order_book = OrderBook()

# @router.websocket("/ws/market_data")
# async def market_data(websocket: WebSocket):
#     await websocket.accept()
#     while True:
#         bbo = order_book.get_bbo()
#         asks, bids = order_book.get_l2_depth()
#         await websocket.send_json({
#             "type": "bbo",
#             "bbo": bbo,
#             "asks": asks,
#             "bids": bids
#         })
#         await asyncio.sleep(1)

# @router.websocket("/ws/trades")
# async def trade_feed(websocket: WebSocket):
#     await websocket.accept()
#     last_sent = 0
#     while True:
#         trades = order_book.trade_log[last_sent:]
#         for trade in trades:
#             await websocket.send_json(trade.to_dict())
#         last_sent += len(trades)
#         await asyncio.sleep(0.5)


from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from typing import Dict, Set, List, Optional
import json
import asyncio
from datetime import datetime
from engine.globals import matching_engine
import logging
from decimal import Decimal

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

router = APIRouter()

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
async def market_data(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for market data updates."""
    try:
        await websocket.accept()
        logger.debug(f"Market data WebSocket connection accepted for {symbol}")
        
        # Normalize symbol format
        symbol = symbol.upper().replace("-", "_")
        
        # Add to active connections
        active_connections["market_data"].append(websocket)
        logger.debug(f"Active market data connections: {len(active_connections['market_data'])}")
        
        # Get matching engine
        engine = matching_engine
        
        # Subscribe to market data updates
        market_data_queue = engine.subscribe("market_data")
        
        try:
            # Send initial market data
            bbo = engine.get_bbo(symbol)
            await websocket.send_json({
                "type": "market_data",
                "data": bbo,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for market data update
                    data = await asyncio.wait_for(market_data_queue.get(), timeout=30.0)
                    
                    # Send update to client
                    await websocket.send_json({
                        "type": "market_data",
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except WebSocketDisconnect:
                    logger.debug("Market data WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"Error in market data WebSocket: {e}", exc_info=True)
                    break
                    
        finally:
            # Cleanup
            engine.unsubscribe("market_data", market_data_queue)
            active_connections["market_data"].remove(websocket)
            logger.debug(f"Market data connection closed. Remaining connections: {len(active_connections['market_data'])}")
            
    except Exception as e:
        logger.error(f"Error in market data WebSocket: {e}", exc_info=True)
        if websocket in active_connections["market_data"]:
            active_connections["market_data"].remove(websocket)

@router.websocket("/ws/trades/{symbol}")
async def trades(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for trade updates."""
    try:
        await websocket.accept()
        logger.debug(f"Trades WebSocket connection accepted for {symbol}")
        
        # Normalize symbol format
        symbol = symbol.upper().replace("-", "_")
        
        # Add to active connections
        active_connections["trades"].append(websocket)
        logger.debug(f"Active trades connections: {len(active_connections['trades'])}")
        
        # Get matching engine
        engine = matching_engine
        
        # Subscribe to trade updates
        trades_queue = engine.subscribe("trades")
        
        try:
            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for trade update
                    data = await asyncio.wait_for(trades_queue.get(), timeout=30.0)
                    
                    # Send update to client
                    await websocket.send_json({
                        "type": "trade",
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    await websocket.send_json({
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except WebSocketDisconnect:
                    logger.debug("Trades WebSocket disconnected")
                    break
                except Exception as e:
                    logger.error(f"Error in trades WebSocket: {e}", exc_info=True)
                    break
                    
        finally:
            # Cleanup
            engine.unsubscribe("trades", trades_queue)
            active_connections["trades"].remove(websocket)
            logger.debug(f"Trades connection closed. Remaining connections: {len(active_connections['trades'])}")
            
    except Exception as e:
        logger.error(f"Error in trades WebSocket: {e}", exc_info=True)
        if websocket in active_connections["trades"]:
            active_connections["trades"].remove(websocket)

@router.websocket("/ws/pending-orders/{symbol}")
async def pending_orders(websocket: WebSocket, symbol: str):
    """WebSocket endpoint for pending orders updates."""
    try:
        await websocket.accept()
        logger.debug(f"Pending orders WebSocket connection accepted for {symbol}")
        
        # Normalize symbol format
        symbol = symbol.upper().replace("-", "_")
        
        # Add to active connections
        active_connections["orders"].append(websocket)
        logger.debug(f"Active orders connections: {len(active_connections['orders'])}")
        
        # Subscribe to order updates using the global matching_engine
        orders_queue = matching_engine.subscribe("orders")
        logger.debug("Subscribed to order updates queue")
        
        try:
            # Send initial pending orders using the global matching_engine
            order_book = matching_engine.get_order_book(symbol)
            pending_orders = order_book.get_pending_orders()
            logger.debug(f"Initial pending orders: {pending_orders}")
            
            initial_message = {
                "type": "pending_orders",
                "data": pending_orders,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await websocket.send_json(initial_message)
            logger.debug("Sent initial pending orders message")
            
            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for order update
                    logger.debug("Waiting for order update...")
                    data = await asyncio.wait_for(orders_queue.get(), timeout=30.0)
                    logger.debug(f"Received order update: {data}")
                    
                    # Get latest pending orders
                    pending_orders = order_book.get_pending_orders()
                    logger.debug(f"Latest pending orders: {pending_orders}")
                    
                    # Send both the order update and latest pending orders
                    update_message = {
                        "type": "order_update",
                        "order": data,
                        "pending_orders": pending_orders,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    
                    await websocket.send_json(update_message)
                    logger.debug("Sent order update message")
                    
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    heartbeat_message = {
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await websocket.send_json(heartbeat_message)
                    logger.debug("Sent heartbeat message")
                    
                except WebSocketDisconnect:
                    logger.debug("Pending orders WebSocket disconnected")
                    break
                    
                except Exception as e:
                    logger.error(f"Error in pending orders WebSocket: {e}", exc_info=True)
                    break
                    
        finally:
            # Cleanup
            logger.debug("Cleaning up WebSocket connection")
            matching_engine.unsubscribe("orders", orders_queue)
            if websocket in active_connections["orders"]:
                active_connections["orders"].remove(websocket)
            logger.debug(f"Pending orders connection closed. Remaining connections: {len(active_connections['orders'])}")
            
    except Exception as e:
        logger.error(f"Error in pending orders WebSocket: {e}", exc_info=True)
        if websocket in active_connections["orders"]:
            active_connections["orders"].remove(websocket)

@router.websocket("/ws/test")
async def test_socket(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_text("Hello from server")
        await asyncio.sleep(1)
