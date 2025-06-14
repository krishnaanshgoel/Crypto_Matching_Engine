from fastapi import WebSocket, WebSocketDisconnect
from typing import Dict, Set, Optional
import asyncio
import logging
from datetime import datetime
from collections import defaultdict
import json
from decimal import Decimal

logger = logging.getLogger(__name__)

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

class WebSocketManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)
        self.connection_states: Dict[str, Dict[str, bool]] = defaultdict(dict)
        self.connection_stats: Dict[str, Dict[str, dict]] = defaultdict(dict)
        self.heartbeat_tasks: Dict[str, Dict[str, asyncio.Task]] = defaultdict(dict)

    async def connect(self, websocket: WebSocket, client_id: str, channel: str):
        """Connect a new client to a specific channel."""
        try:
            await websocket.accept()
            self.active_connections[channel][client_id] = websocket
            self.connection_states[channel][client_id] = True
            self.connection_stats[channel][client_id] = {
                'connected_at': datetime.utcnow(),
                'last_activity': datetime.utcnow(),
                'messages_sent': 0,
                'messages_received': 0,
                'errors': 0
            }
            
            # Start heartbeat for this connection
            self.heartbeat_tasks[channel][client_id] = asyncio.create_task(
                self._heartbeat(channel, client_id)
            )
            
            logger.info(f"Client {client_id} connected to channel {channel}")
        except Exception as e:
            logger.error(f"Error connecting client {client_id} to channel {channel}: {e}")
            raise

    async def disconnect(self, client_id: str, channel: str):
        """Disconnect a client from a specific channel."""
        try:
            if client_id in self.heartbeat_tasks[channel]:
                self.heartbeat_tasks[channel][client_id].cancel()
                del self.heartbeat_tasks[channel][client_id]
            
            if client_id in self.active_connections[channel]:
                self.connection_states[channel][client_id] = False
                del self.active_connections[channel][client_id]
                del self.connection_states[channel][client_id]
                
                # Log connection duration
                if client_id in self.connection_stats[channel]:
                    duration = datetime.utcnow() - self.connection_stats[channel][client_id]['connected_at']
                    logger.info(f"Client {client_id} disconnected from {channel} after {duration}")
                    del self.connection_stats[channel][client_id]
        except Exception as e:
            logger.error(f"Error disconnecting client {client_id} from channel {channel}: {e}")

    async def send_message(self, channel: str, message: str, exclude_client: Optional[str] = None):
        """Send a message to all clients in a channel."""
        disconnected_clients = set()
        
        for client_id, websocket in self.active_connections[channel].items():
            if client_id == exclude_client:
                continue
                
            if self.connection_states[channel][client_id]:
                try:
                    await websocket.send_text(message)
                    self.connection_stats[channel][client_id]['messages_sent'] += 1
                    self.connection_stats[channel][client_id]['last_activity'] = datetime.utcnow()
                except WebSocketDisconnect:
                    disconnected_clients.add(client_id)
                except Exception as e:
                    logger.error(f"Error sending message to client {client_id} in channel {channel}: {e}")
                    self.connection_stats[channel][client_id]['errors'] += 1
                    disconnected_clients.add(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id, channel)

    async def _heartbeat(self, channel: str, client_id: str):
        """Send periodic heartbeat to keep connection alive."""
        while True:
            try:
                if client_id in self.active_connections[channel]:
                    await self.send_message(
                        channel,
                        json.dumps({"type": "heartbeat", "timestamp": datetime.utcnow().isoformat()}),
                        exclude_client=client_id
                    )
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat for client {client_id} in channel {channel}: {e}")
                break

    def get_connection_stats(self, channel: str) -> Dict:
        """Get statistics for all connections in a channel."""
        return {
            'total_connections': len(self.active_connections[channel]),
            'active_connections': sum(1 for state in self.connection_states[channel].values() if state),
            'connection_details': self.connection_stats[channel]
        }

    async def broadcast_market_data(self, channel: str, data: dict, bbo: dict):
        """Broadcast market data to all clients in a channel."""
        message = json.dumps({
            "type": "market_data",
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
            "bbo": bbo
        }, cls=DecimalEncoder)
        await self.send_message(channel, message)

    async def broadcast_trade(self, channel: str, trade: dict):
        """Broadcast trade data to all clients in a channel."""
        message = json.dumps({
            "type": "trade",
            "data": trade,
            "timestamp": datetime.utcnow().isoformat()
        }, cls=DecimalEncoder)
        await self.send_message(channel, message)

    async def broadcast_order(self, channel: str, order: dict, data: dict):
        """Broadcast order update to all clients in a channel."""
        print("order", order)
        message = json.dumps({
            "type": "order_update",
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }, cls=DecimalEncoder)
        await self.send_message(channel, message) 