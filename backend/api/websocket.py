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


from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Set
import json
import asyncio
from datetime import datetime
from engine.matching_engine import get_or_create_engine

router = APIRouter()

# Store active connections
active_connections: Dict[str, Set[WebSocket]] = {
    "market_data": set(),
    "trades": set(),
    "orders": set()
}

async def broadcast_market_data(symbol: str):
    """Broadcast market data to all connected clients"""
    while True:
        try:
            engine = get_or_create_engine()
            order_book = engine.get_order_book(symbol)
            if not order_book:
                await asyncio.sleep(1)
                continue

            depth_data = order_book.get_top_levels(10)  # Get top 10 levels
            
            market_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
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
                active_connections["market_data"].discard(connection)
            
            await asyncio.sleep(1)  # Update every second
        except Exception as e:
            print(f"Error in market data broadcast: {e}")
            await asyncio.sleep(1)

@router.websocket("/ws/market-data/{symbol}")
async def market_data(websocket: WebSocket, symbol: str):
    try:
        await websocket.accept()
        # await websocket.send_text("Connected successfully!")
        active_connections["market_data"].add(websocket)
        
        # Start market data broadcast for this symbol
        broadcast_task = asyncio.create_task(broadcast_market_data(symbol))
        
        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any incoming messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in market data websocket: {e}")
                break
    except Exception as e:
        print(f"Error accepting market data websocket: {e}")
    finally:
        active_connections["market_data"].discard(websocket)
        if 'broadcast_task' in locals():
            broadcast_task.cancel()

@router.websocket("/ws/trades/{symbol}")
async def trade_feed(websocket: WebSocket, symbol: str):
    try:
        await websocket.accept()
        active_connections["trades"].add(websocket)
        
        engine = get_or_create_engine()
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any incoming messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in trade feed websocket: {e}")
                break
    except Exception as e:
        print(f"Error accepting trade feed websocket: {e}")
    finally:
        active_connections["trades"].discard(websocket)
        engine.unsubscribe_trades(websocket, symbol)

@router.websocket("/ws/orders/{symbol}")
async def order_feed(websocket: WebSocket, symbol: str):
    try:
        await websocket.accept()
        active_connections["orders"].add(websocket)
        
        engine = get_or_create_engine()
        while True:
            try:
                data = await websocket.receive_text()
                # Handle any incoming messages if needed
            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"Error in order feed websocket: {e}")
                break
    except Exception as e:
        print(f"Error accepting order feed websocket: {e}")
    finally:
        active_connections["orders"].discard(websocket)
        engine.unsubscribe_orders(websocket, symbol)


@router.websocket("/ws/test")
async def test_socket(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_text("Hello from server")
        await asyncio.sleep(1)
