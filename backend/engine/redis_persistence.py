import json
import redis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool
from typing import Dict, List, Optional
from decimal import Decimal
from datetime import datetime
import logging
import asyncio
from functools import lru_cache

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade
from engine.order_book import OrderBook, PriceLevel

logger = logging.getLogger(__name__)

class RedisPersistence:
    def __init__(self, redis_url: str):
        """Initialize Redis connection with connection pooling."""
        self.pool = ConnectionPool.from_url(redis_url, max_connections=10)
        self.redis = Redis(connection_pool=self.pool)
        logger.info("Redis connection pool initialized")

    def _serialize_order(self, order: Order) -> str:
        """Serialize an order to JSON."""
        return json.dumps({
            'id': order.id,
            'symbol': order.symbol,
            'side': order.side.value,
            'order_type': order.order_type.value,
            'quantity': str(order.quantity),
            'price': str(order.price) if order.price else None,
            'stop_price': str(order.stop_price) if order.stop_price else None,
            'status': order.status,
            'filled_quantity': str(order.filled_quantity),
            'timestamp': order.timestamp.isoformat(),
            'triggered': order.triggered
        })

    def _deserialize_order(self, data: str) -> Order:
        """Deserialize JSON to an Order object."""
        order_dict = json.loads(data)
        return Order(
            id=order_dict['id'],
            symbol=order_dict['symbol'],
            side=OrderSide(order_dict['side']),
            order_type=OrderType(order_dict['order_type']),
            quantity=Decimal(order_dict['quantity']),
            price=Decimal(order_dict['price']) if order_dict['price'] else None,
            stop_price=Decimal(order_dict['stop_price']) if order_dict['stop_price'] else None,
            status=order_dict['status'],
            filled_quantity=Decimal(order_dict['filled_quantity']),
            timestamp=datetime.fromisoformat(order_dict['timestamp']),
            triggered=order_dict['triggered']
        )

    async def save_order_book(self, symbol: str, order_book: OrderBook) -> None:
        """Save the entire order book state to Redis using batching."""
        try:
            async with self.redis.pipeline() as pipe:
                # Save bids
                for price, level in order_book.bids.items():
                    key = f"orderbook:{symbol}:bids:{price}"
                    orders = [self._serialize_order(order) for order in level.orders]
                    if orders:
                        await pipe.sadd(key, *orders)
                        await pipe.expire(key, 86400)  # 24 hours expiry

                # Save asks
                for price, level in order_book.asks.items():
                    key = f"orderbook:{symbol}:asks:{price}"
                    orders = [self._serialize_order(order) for order in level.orders]
                    if orders:
                        await pipe.sadd(key, *orders)
                        await pipe.expire(key, 86400)

                # Save inactive orders
                for order_id, order in order_book.inactive_orders.items():
                    key = f"orderbook:{symbol}:inactive"
                    await pipe.hset(key, order_id, self._serialize_order(order))
                    await pipe.expire(key, 86400)

                # Execute all commands in one go
                await pipe.execute()
                logger.info(f"Order book state saved for {symbol}")
        except Exception as e:
            logger.error(f"Error saving order book state: {e}", exc_info=True)

    @lru_cache(maxsize=100)
    async def load_order_book(self, symbol: str) -> Optional[OrderBook]:
        """Load the order book state from Redis with caching."""
        try:
            order_book = OrderBook(symbol)

            # Load bids
            bid_keys = await self.redis.keys(f"orderbook:{symbol}:bids:*")
            for key in bid_keys:
                price = Decimal(key.split(':')[-1])
                orders_data = await self.redis.smembers(key)
                if orders_data:
                    price_level = PriceLevel(price)
                    for order_data in orders_data:
                        order = self._deserialize_order(order_data)
                        price_level.add_order(order)
                    order_book.bids[price] = price_level

            # Load asks
            ask_keys = await self.redis.keys(f"orderbook:{symbol}:asks:*")
            for key in ask_keys:
                price = Decimal(key.split(':')[-1])
                orders_data = await self.redis.smembers(key)
                if orders_data:
                    price_level = PriceLevel(price)
                    for order_data in orders_data:
                        order = self._deserialize_order(order_data)
                        price_level.add_order(order)
                    order_book.asks[price] = price_level

            # Load inactive orders
            inactive_key = f"orderbook:{symbol}:inactive"
            inactive_orders = await self.redis.hgetall(inactive_key)
            for order_id, order_data in inactive_orders.items():
                order = self._deserialize_order(order_data)
                order_book.inactive_orders[order_id] = order

            # Update best bid/ask
            if order_book.bids:
                order_book._best_bid = max(order_book.bids.values(), key=lambda x: x.price)
            if order_book.asks:
                order_book._best_ask = min(order_book.asks.values(), key=lambda x: x.price)

            logger.info(f"Order book state loaded for {symbol}")
            return order_book
        except Exception as e:
            logger.error(f"Error loading order book state: {e}", exc_info=True)
            return None

    async def save_trade(self, trade: Trade) -> None:
        """Save a trade to Redis using batching."""
        try:
            trade_data = {
                'id': trade.id,
                'symbol': trade.symbol,
                'price': str(trade.price),
                'quantity': str(trade.quantity),
                'buy_order_id': trade.buy_order_id,
                'sell_order_id': trade.sell_order_id,
                'side': trade.side.value,
                'timestamp': datetime.utcnow().isoformat()
            }
            key = f"trades:{trade.symbol}"
            async with self.redis.pipeline() as pipe:
                await pipe.lpush(key, json.dumps(trade_data))
                await pipe.ltrim(key, 0, 999)  # Keep last 1000 trades
                await pipe.expire(key, 86400)  # 24 hours expiry
                await pipe.execute()
            logger.info(f"Trade {trade.id} saved")
        except Exception as e:
            logger.error(f"Error saving trade: {e}", exc_info=True)

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """Get recent trades for a symbol."""
        try:
            key = f"trades:{symbol}"
            trades_data = await self.redis.lrange(key, 0, limit - 1)
            trades = []
            for trade_data in trades_data:
                trade_dict = json.loads(trade_data)
                trades.append(Trade(
                    id=trade_dict['id'],
                    symbol=trade_dict['symbol'],
                    price=Decimal(trade_dict['price']),
                    quantity=Decimal(trade_dict['quantity']),
                    buy_order_id=trade_dict['buy_order_id'],
                    sell_order_id=trade_dict['sell_order_id'],
                    side=OrderSide(trade_dict['side'])
                ))
            return trades
        except Exception as e:
            logger.error(f"Error getting recent trades: {e}", exc_info=True)
            return [] 