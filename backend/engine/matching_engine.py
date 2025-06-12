from decimal import Decimal
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime
from collections import defaultdict
import json
import asyncio
from uuid import uuid4
from fastapi import WebSocket

from engine.base_models import Order, OrderSide, OrderType
from engine.models import Trade, BBO
from engine.order_book import OrderBook

class MatchingEngine:
    def __init__(self):
        self.order_books: Dict[str, OrderBook] = {}
        self.market_data_subscribers: Dict[str, Set[Callable[[str], Any]]] = defaultdict(set)
        self.trade_subscribers: Dict[str, Set[Callable[[str], Any]]] = defaultdict(set)
        self.order_subscribers: Dict[str, Set[Callable[[str], Any]]] = defaultdict(set)

    def get_order_book(self, symbol: str) -> OrderBook:
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]

    async def process_order(self, order: Order) -> List[Trade]:
        order_book = self.get_order_book(order.symbol)
        trades = []

        if order.order_type == OrderType.MARKET:
            trades.extend(self._process_market_order(order, order_book))
        elif order.order_type == OrderType.LIMIT:
            trades.extend(self._process_limit_order(order, order_book))
        elif order.order_type == OrderType.IOC:
            trades.extend(self._process_ioc_order(order, order_book))
        elif order.order_type == OrderType.FOK:
            trades.extend(self._process_fok_order(order, order_book))

        if trades:
            for trade in trades:
                await self._broadcast_trade(trade)
        await self._broadcast_market_data(order.symbol)
        await self._broadcast_order(order)

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
                    sell_order_id=matching_order.id
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
                    sell_order_id=order.id
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
                    sell_order_id=matching_order.id
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
                    sell_order_id=order.id
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
                    sell_order_id=matching_order.id
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
                    sell_order_id=order.id
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
                    sell_order_id=matching_order.id
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
                    sell_order_id=order.id
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
        for order_book in self.order_books.values():
            order = order_book.remove_order(order_id)
            if order:
                order.status = "CANCELLED"
                self._broadcast_market_data(order.symbol)
                self._broadcast_order(order)
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
        """Broadcast market data to all subscribers."""
        if symbol not in self.market_data_subscribers:
            return

        order_book = self.order_books[symbol]
        best_bid = order_book.get_best_bid()
        best_ask = order_book.get_best_ask()
        
        # Convert Decimal values to strings
        market_data = {
            'best_bid': str(best_bid.price) if best_bid else None,
            'best_bid_quantity': str(best_bid.total_quantity) if best_bid else None,
            'best_ask': str(best_ask.price) if best_ask else None,
            'best_ask_quantity': str(best_ask.total_quantity) if best_ask else None,
            'bids': [
                {'price': str(price), 'quantity': str(level.total_quantity)}
                for price, level in order_book.bids.items()
                if level.total_quantity > 0
            ],
            'asks': [
                {'price': str(price), 'quantity': str(level.total_quantity)}
                for price, level in order_book.asks.items()
                if level.total_quantity > 0
            ]
        }

        for subscriber in self.market_data_subscribers[symbol]:
            try:
                await subscriber.send_json(market_data)
            except Exception as e:
                print(f"Broadcast error: {e}")

    async def _broadcast_trade(self, trade: Trade) -> None:
        """Broadcast trade to all subscribers."""
        if trade.symbol not in self.trade_subscribers:
            return

        # Convert Decimal values to strings
        trade_data = {
            'price': str(trade.price),
            'quantity': str(trade.quantity),
            'side': trade.side.value,
            'timestamp': trade.timestamp.isoformat(),
            'buy_order_id': trade.buy_order_id,
            'sell_order_id': trade.sell_order_id
        }

        for subscriber in self.trade_subscribers[trade.symbol]:
            try:
                await subscriber.send_json(trade_data)
            except Exception as e:
                print(f"Broadcast error: {e}")

    async def _broadcast_order(self, order: Order) -> None:
        """Broadcast order to all subscribers."""
        if order.symbol not in self.order_subscribers:
            return

        # Convert Decimal values to strings
        order_data = {
            'order_id': order.order_id,
            'symbol': order.symbol,
            'side': order.side.value,
            'order_type': order.order_type.value,
            'quantity': str(order.quantity),
            'price': str(order.price) if order.price else None,
            'status': order.status.value,
            'timestamp': order.timestamp.isoformat()
        }

        for subscriber in self.order_subscribers[order.symbol]:
            try:
                await subscriber.send_json(order_data)
            except Exception as e:
                print(f"Broadcast error: {e}")

    async def subscribe_market_data(self, websocket: WebSocket, symbol: str) -> None:
        await websocket.accept()
        self.market_data_subscribers[symbol].add(lambda msg: asyncio.create_task(websocket.send_text(msg)))
        self._broadcast_market_data(symbol)

    def unsubscribe_market_data(self, websocket: WebSocket, symbol: str) -> None:
        self.market_data_subscribers[symbol].discard(lambda msg: asyncio.create_task(websocket.send_text(msg)))

    async def subscribe_trades(self, websocket: WebSocket, symbol: str) -> None:
        await websocket.accept()
        self.trade_subscribers[symbol].add(lambda msg: asyncio.create_task(websocket.send_text(msg)))

    def unsubscribe_trades(self, websocket: WebSocket, symbol: str) -> None:
        self.trade_subscribers[symbol].discard(lambda msg: asyncio.create_task(websocket.send_text(msg)))

    async def subscribe_orders(self, websocket: WebSocket, symbol: str) -> None:
        await websocket.accept()
        self.order_subscribers[symbol].add(lambda msg: asyncio.create_task(websocket.send_text(msg)))

    def unsubscribe_orders(self, websocket: WebSocket, symbol: str) -> None:
        self.order_subscribers[symbol].discard(lambda msg: asyncio.create_task(websocket.send_text(msg)))

    def get_bbo(self, symbol: str = "BTC_USD") -> Dict:
        """Get the Best Bid/Offer (BBO) for a symbol."""
        if symbol not in self.order_books:
            return {
                "best_bid": None,
                "best_bid_quantity": None,
                "best_ask": None,
                "best_ask_quantity": None
            }

        order_book = self.order_books[symbol]
        best_bid = order_book.get_best_bid()
        best_ask = order_book.get_best_ask()

        return {
            "best_bid": str(best_bid.price) if best_bid else None,
            "best_bid_quantity": str(best_bid.total_quantity) if best_bid else None,
            "best_ask": str(best_ask.price) if best_ask else None,
            "best_ask_quantity": str(best_ask.total_quantity) if best_ask else None
        }

    def get_order_book(self, symbol: str = "BTC_USD") -> Dict:
        if symbol not in self.order_books:
            self.order_books[symbol] = OrderBook(symbol)
        return self.order_books[symbol]
