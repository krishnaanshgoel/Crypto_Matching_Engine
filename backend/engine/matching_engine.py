from decimal import Decimal
from typing import Dict, List, Optional, Set, Callable, Any, Tuple
from datetime import datetime, UTC
from collections import defaultdict
import json
import asyncio
from uuid import uuid4
from fastapi import WebSocket
import logging

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade, BBO
from engine.order_book import OrderBook

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global dictionary to store engine instances
engines = {}

def get_or_create_engine(symbol: str) -> OrderBook:
    """Get or create an OrderBook instance for the given symbol."""
    if symbol not in engines:
        engines[symbol] = OrderBook(symbol)
    return engines[symbol]

class MatchingEngine:
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}
        self.subscribers: Dict[str, Set[asyncio.Queue]] = {
            "market_data": set(),
            "trades": set(),
            "orders": set()
        }
        logger.debug("MatchingEngine initialized")

    def get_order_book(self, symbol: str) -> OrderBook:
        """Get or create an order book for a symbol."""
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
            logger.debug(f"Created new order book for {symbol}")
        return self.order_books[symbol]

    async def process_activated_order(self, activated_order: Order, current_order: Order = None) -> List[Trade]:
        """Process an activated order, potentially matching against the current order."""
        trades = []
        order_book = self.get_order_book(activated_order.symbol)

        # If we have a current order and it can match with the activated order
        if current_order and self._can_orders_match(activated_order, current_order):
            # Match the activated order against the current order
            trade_quantity = min(activated_order.quantity, current_order.quantity)
            trade_price = current_order.price if current_order.order_type != OrderType.MARKET else (
                order_book.get_best_ask().price if activated_order.side == OrderSide.BUY 
                else order_book.get_best_bid().price
            )

            trade = Trade(
                id=str(uuid4()),
                symbol=activated_order.symbol,
                price=trade_price,
                quantity=trade_quantity,
                buy_order_id=activated_order.id if activated_order.side == OrderSide.BUY else current_order.id,
                sell_order_id=current_order.id if activated_order.side == OrderSide.BUY else activated_order.id,
                side=activated_order.side
            )
            trades.append(trade)

            # Update quantities
            activated_order.quantity -= trade_quantity
            activated_order.filled_quantity += trade_quantity
            current_order.quantity -= trade_quantity
            current_order.filled_quantity += trade_quantity

            # Update statuses
            if activated_order.quantity == 0:
                activated_order.status = "FILLED"
            else:
                activated_order.status = "PARTIALLY_FILLED"

            if current_order.quantity == 0:
                current_order.status = "FILLED"
            else:
                current_order.status = "PARTIALLY_FILLED"

        # If activated order still has quantity, process it normally
        if activated_order.quantity > 0:
            if activated_order.order_type == OrderType.MARKET:
                trades.extend(order_book.match_order(activated_order))
            elif activated_order.order_type == OrderType.LIMIT:
                trades.extend(order_book.match_order(activated_order))
                if activated_order.quantity > 0:
                    order_book.add_order(activated_order)
            elif activated_order.order_type in [OrderType.IOC, OrderType.FOK]:
                trades.extend(order_book.match_order(activated_order))

        return trades

    def _can_orders_match(self, order1: Order, order2: Order) -> bool:
        """Check if two orders can match with each other."""
        if order1.side == order2.side:
            return False

        # For market orders, they can always match
        if order1.order_type == OrderType.MARKET or order2.order_type == OrderType.MARKET:
            return True

        # For limit orders, check if prices cross
        if order1.side == OrderSide.BUY:
            return order1.price >= order2.price
        else:
            return order1.price <= order2.price

    async def process_order(self, order: Order) -> List[Trade]:
        """Process a new order."""
        logger.debug(f"Processing order: {order.id} for {order.symbol}")
        order_book = self.get_order_book(order.symbol)
        trades = []

        # Check for inactive orders that should be triggered
        price = order.price if order.price is not None else order_book.get_best_bid_ask()[0]
        activated_orders = order_book.check_inactive_orders(price)
        print("activated_orders", activated_orders)

        # Process activated orders first, potentially matching against the current order
        for activated_order in activated_orders:
            activated_trades = await self.process_activated_order(activated_order, order)
            trades.extend(activated_trades)

        # Process the new order
        # if order.order_type == OrderType.MARKET:
        #     trades.extend(order_book.match_order(order))
        #     if order.quantity > 0:
        #         order_book.add_order(order)
        if order.quantity<=0:
            return trades
        if order.order_type == OrderType.LIMIT:
            trades.extend(order_book.match_order(order))
            if order.quantity > 0:
                order_book.add_order(order)
        elif order.order_type == OrderType.IOC or order.order_type == OrderType.MARKET:
            trades.extend(order_book.match_order(order))
            if order.quantity > 0:
                order_book.remove_order(order.id)
        elif order.order_type == OrderType.FOK :
            # For FOK, we need to check if we can fill the entire order before executing
            if order.side == OrderSide.BUY:
                total_available = Decimal('0')
                for price_level in order_book.asks.values():
                    for ask_order in price_level.orders:
                        if order.price is not None and ask_order.price > order.price:
                            break
                        total_available += ask_order.quantity
                        if total_available >= order.quantity:
                            break
                    if total_available >= order.quantity:
                        break
                if total_available >= order.quantity:
                    trades.extend(order_book.match_order(order))
            else:  # SELL
                total_available = Decimal('0')
                for price_level in order_book.bids.values():
                    for bid_order in price_level.orders:
                        if order.price is not None and bid_order.price < order.price:
                            break
                        total_available += bid_order.quantity
                        if total_available >= order.quantity:
                            break
                    if total_available >= order.quantity:
                        break
                if total_available >= order.quantity:
                    trades.extend(order_book.match_order(order))
        elif order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT]:
            order_book.add_order(order)
        
        print("order_book", order_book)

        # Broadcast updates
        logger.debug(f"Broadcasting updates for order {order.id}")
        try:
            await self._broadcast_market_data(order.symbol)
            logger.debug("Market data broadcast complete")
            
            await self._broadcast_trades(trades)
            logger.debug("Trades broadcast complete")
            
            await self._broadcast_order(order)
            logger.debug("Order broadcast complete")
        except Exception as e:
            logger.error(f"Error broadcasting updates: {e}", exc_info=True)

        logger.debug(f"Order {order.id} processed and added to order book for {order.symbol}")

        return trades

    def _process_market_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        trades = []
        remaining_quantity = order.quantity

        if order.side == OrderSide.BUY:
            while remaining_quantity > 0 and order_book.get_best_ask():
                best_ask = order_book.get_best_ask()
                if not best_ask or not best_ask.orders:
                    break

                matching_order = best_ask.orders[0]
                trade_quantity = min(remaining_quantity, matching_order.quantity)
                trade_price = best_ask.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=order.id,
                    sell_order_id=matching_order.id,
                    side=OrderSide.BUY
                )
                trades.append(trade)

                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    best_ask.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        else:  # SELL
            while remaining_quantity > 0 and order_book.get_best_bid():
                best_bid = order_book.get_best_bid()
                if not best_bid or not best_bid.orders:
                    break

                matching_order = best_bid.orders[0]
                trade_quantity = min(remaining_quantity, matching_order.quantity)
                trade_price = best_bid.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=matching_order.id,
                    sell_order_id=order.id,
                    side=OrderSide.SELL
                )
                trades.append(trade)

                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    best_bid.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        if remaining_quantity > 0:
            order.quantity = remaining_quantity
            order.status = "PARTIALLY_FILLED"
        else:
            order.status = "FILLED"

        return trades

    def _process_limit_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        trades = []
        remaining_quantity = order.quantity

        if order.side == OrderSide.BUY:
            while remaining_quantity > 0 and order_book.get_best_ask() and order.price >= order_book.get_best_ask().price:
                best_ask = order_book.get_best_ask()
                if not best_ask.orders:
                    break

                matching_order = best_ask.orders[0]
                trade_quantity = min(remaining_quantity, matching_order.quantity)
                trade_price = best_ask.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=order.id,
                    sell_order_id=matching_order.id,
                    side=OrderSide.BUY
                )
                trades.append(trade)

                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    best_ask.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        else:  # SELL
            while remaining_quantity > 0 and order_book.get_best_bid() and order.price <= order_book.get_best_bid().price:
                best_bid = order_book.get_best_bid()
                if not best_bid.orders:
                    break

                matching_order = best_bid.orders[0]
                trade_quantity = min(remaining_quantity, matching_order.quantity)
                trade_price = best_bid.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=matching_order.id,
                    sell_order_id=order.id,
                    side=OrderSide.SELL
                )
                trades.append(trade)

                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    best_bid.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        if remaining_quantity > 0:
            order.quantity = remaining_quantity
            order_book.add_order(order)
            order.status = "PARTIALLY_FILLED"
        else:
            order.status = "FILLED"

        return trades

    def _process_ioc_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Process an Immediate-or-Cancel (IOC) order.
        - Executes against available orders at the specified price
        - Cancels any remaining quantity
        - Keeps the executed trades
        """
        trades = []
        remaining_quantity = order.quantity

        if order.side == OrderSide.BUY:
            while remaining_quantity > 0 and order_book.get_best_ask() and order.price >= order_book.get_best_ask().price:
                best_ask = order_book.get_best_ask()
                if not best_ask or not best_ask.orders:
                    break

                matching_order = best_ask.orders[0]
                trade_quantity = min(remaining_quantity, matching_order.quantity)
                trade_price = best_ask.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=order.id,
                    sell_order_id=matching_order.id,
                    side=OrderSide.BUY
                )
                trades.append(trade)

                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    best_ask.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        else:  # SELL
            while remaining_quantity > 0 and order_book.get_best_bid() and order.price <= order_book.get_best_bid().price:
                best_bid = order_book.get_best_bid()
                if not best_bid or not best_bid.orders:
                    break

                matching_order = best_bid.orders[0]
                trade_quantity = min(remaining_quantity, matching_order.quantity)
                trade_price = best_bid.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=matching_order.id,
                    sell_order_id=order.id,
                    side=OrderSide.SELL
                )
                trades.append(trade)

                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    best_bid.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        if remaining_quantity > 0:
            order.status = "CANCELLED"
        else:
            order.status = "FILLED"

        return trades

    def _process_fok_order(self, order: Order, order_book: OrderBook) -> List[Trade]:
        """Process a Fill-or-Kill (FOK) order.
        - Only executes if the entire order can be filled
        - If not fully filled, cancels the entire order and returns no trades
        """
        trades = []
        remaining_quantity = order.quantity
        original_quantity = order.quantity

        if order.side == OrderSide.BUY:
            # First check if we can fill the entire order
            temp_quantity = original_quantity
            temp_asks = []
            
            # Check all available asks that match our price
            for price, level in sorted(order_book.asks.items()):
                if price > order.price or temp_quantity <= 0:
                    break
                    
                for matching_order in level.orders:
                    if temp_quantity <= 0:
                        break
                        
                    trade_quantity = min(temp_quantity, matching_order.quantity)
                    temp_quantity -= trade_quantity
                    temp_asks.append((level, matching_order, trade_quantity))

            # If we can't fill the entire order, return empty trades
            if temp_quantity > 0:
                order.status = "CANCELLED"
                return trades

            # Execute the trades since we can fill the entire order
            for level, matching_order, trade_quantity in temp_asks:
                trade_price = level.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=order.id,
                    sell_order_id=matching_order.id,
                    side=OrderSide.BUY
                )
                trades.append(trade)

                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    level.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        else:  # SELL
            # First check if we can fill the entire order
            temp_quantity = original_quantity
            temp_bids = []
            
            # Check all available bids that match our price
            for price, level in sorted(order_book.bids.items(), reverse=True):
                if price < order.price or temp_quantity <= 0:
                    break
                    
                for matching_order in level.orders:
                    if temp_quantity <= 0:
                        break
                        
                    trade_quantity = min(temp_quantity, matching_order.quantity)
                    temp_quantity -= trade_quantity
                    temp_bids.append((level, matching_order, trade_quantity))

            # If we can't fill the entire order, return empty trades
            if temp_quantity > 0:
                order.status = "CANCELLED"
                return trades

            # Execute the trades since we can fill the entire order
            for level, matching_order, trade_quantity in temp_bids:
                trade_price = level.price

                trade = Trade(
                    id=str(uuid4()),
                    symbol=order.symbol,
                    price=trade_price,
                    quantity=trade_quantity,
                    buy_order_id=matching_order.id,
                    sell_order_id=order.id,
                    side=OrderSide.SELL
                )
                trades.append(trade)

                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                if matching_order.quantity == 0:
                    level.remove_order(matching_order)
                    matching_order.status = "FILLED"
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        order.status = "FILLED"
        return trades

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        for order_book in self.order_books.values():
            order = order_book.remove_order(order_id)
            if order:
                order.status = "CANCELLED"
                asyncio.create_task(self._broadcast_market_data(order.symbol))
                asyncio.create_task(self._broadcast_order(order))
                return True
        return False

    def _convert_decimal_to_str(self, data):
        """Convert Decimal values to strings in the data structure."""
        if isinstance(data, Decimal):
            return str(data)
        elif isinstance(data, dict):
            return {k: self._convert_decimal_to_str(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._convert_decimal_to_str(item) for item in data]
        return data

    async def _broadcast_market_data(self, symbol: str) -> None:
        """Broadcast market data updates to subscribers."""
        order_book = self.get_order_book(symbol)
        snapshot = order_book.get_order_book_snapshot()
        
        for queue in self.subscribers["market_data"]:
            await queue.put(snapshot)

    async def _broadcast_trades(self, trades: List[Trade]) -> None:
        """Broadcast trade updates to subscribers."""
        for trade in trades:
            for queue in self.subscribers["trades"]:
                await queue.put(trade.dict())

    async def _broadcast_order(self, order: Order) -> None:
        """Broadcast order updates to subscribers."""
        logger.debug(f"Broadcasting order update for {order.id}")
        order_data = {
            "type": "order_update",
            "symbol": order.symbol,
            "order_id": order.id,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "filled_quantity": str(order.filled_quantity),
            "status": order.status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add optional fields if present
        if order.price is not None:
            order_data["price"] = str(order.price)
        if order.stop_price is not None:
            order_data["stop_price"] = str(order.stop_price)
            
        # Convert to string format for JSON serialization
        order_data = self._convert_decimal_to_str(order_data)
        
        logger.debug(f"Order data to broadcast: {order_data}")
        logger.debug(f"Number of subscribers: {len(self.subscribers['orders'])}")
        
        # Create a copy of subscribers to avoid modification during iteration
        subscribers = list(self.subscribers["orders"])
        
        for queue in subscribers:
            try:
                logger.debug(f"Attempting to send order update to subscriber queue")
                await queue.put(order_data)
                logger.debug(f"Successfully sent order update to subscriber queue")
            except Exception as e:
                logger.error(f"Error broadcasting order update: {e}", exc_info=True)
                # Remove failed subscriber
                self.subscribers["orders"].discard(queue)

    def subscribe(self, channel: str) -> asyncio.Queue:
        """Subscribe to a channel."""
        queue = asyncio.Queue()
        self.subscribers[channel].add(queue)
        logger.debug(f"New subscription to {channel}. Total subscribers: {len(self.subscribers[channel])}")
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        """Unsubscribe from a channel."""
        if queue in self.subscribers[channel]:
            self.subscribers[channel].remove(queue)
            logger.debug(f"Unsubscribed from {channel}. Remaining subscribers: {len(self.subscribers[channel])}")
        else:
            logger.warning(f"Attempted to unsubscribe non-existent queue from {channel}")

    def get_bbo(self, symbol: str) -> Dict:
        """Get the best bid and offer (BBO)."""
        order_book = self.get_order_book(symbol)
        best_bid = order_book.get_best_bid()
        best_ask = order_book.get_best_ask()
        
        return {
            "best_bid": float(best_bid.price) if best_bid else None,
            "best_bid_quantity": float(best_bid.quantity) if best_bid else None,
            "best_ask": float(best_ask.price) if best_ask else None,
            "best_ask_quantity": float(best_ask.quantity) if best_ask else None,
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_order_book(self, symbol: str = "BTC_USD") -> Dict:
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]

__all__ = ['OrderBook', 'MatchingEngine', 'get_or_create_engine']
