from datetime import datetime, UTC
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from uuid import uuid4
import logging

from engine.base_models import Order, OrderSide, OrderType, Trade

logger = logging.getLogger(__name__)

class PriceLevel:
    def __init__(self, price: Decimal):
        self.price = price
        self.orders: List[Order] = []
        self.total_quantity = Decimal('0')

    def add_order(self, order: Order):
        self.orders.append(order)
        self.total_quantity += order.quantity

    def remove_order(self, order_id: str) -> Optional[Order]:
        for i, order in enumerate(self.orders):
            if order.id == order_id:
                removed_order = self.orders.pop(i)
                self.total_quantity -= removed_order.quantity
                return removed_order
        return None

    def update_quantity(self, order_id: str, new_quantity: Decimal) -> bool:
        for order in self.orders:
            if order.id == order_id:
                self.total_quantity = self.total_quantity - order.quantity + new_quantity
                order.quantity = new_quantity
                return True
        return False

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[Decimal, PriceLevel] = {}  # price -> PriceLevel
        self.asks: Dict[Decimal, PriceLevel] = {}  # price -> PriceLevel
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.inactive_orders: Dict[str, Order] = {}  # order_id -> Order
        self._best_bid: Optional[PriceLevel] = None
        self._best_ask: Optional[PriceLevel] = None

    def add_order(self, order: Order) -> None:
        """Add an order to the order book."""
        logger.debug(f"Adding order {order.id} to order book for {order.symbol}")
        if order.order_type in [OrderType.STOP_LOSS, OrderType.STOP_LIMIT, OrderType.TAKE_PROFIT]:
            # print("order", order)
            # print("before add orders")
            self.inactive_orders[order.id] = order
            # print("order", self.inactive_orders)
            logger.debug(f"Order {order.id} added to inactive orders")
            return

        # Store the order in the orders dictionary
        self.orders[order.id] = order
        logger.debug(f"Order {order.id} stored in orders dictionary")

        # Add to the appropriate side (bids or asks)
        price_levels = self.bids if order.side == OrderSide.BUY else self.asks
        
        # Create price level if it doesn't exist
        if order.price not in price_levels:
            price_levels[order.price] = PriceLevel(order.price)
            logger.debug(f"Created new price level for {order.price}")
        
        # Add the order to the price level
        price_levels[order.price].add_order(order)
        logger.debug(f"Order {order.id} added to price level {order.price}")

        # Update best bid/ask if necessary
        if order.side == OrderSide.BUY:
            if self._best_bid is None or order.price > self._best_bid.price:
                self._best_bid = price_levels[order.price]
                logger.debug(f"Updated best bid to {order.price}")
        else:  # SELL
            if self._best_ask is None or order.price < self._best_ask.price:
                self._best_ask = price_levels[order.price]
                logger.debug(f"Updated best ask to {order.price}")

    def remove_order(self, order_id: str) -> Optional[Order]:
        """Remove an order from the order book."""
        # Check inactive orders first
        if order_id in self.inactive_orders:
            return self.inactive_orders.pop(order_id)

        # Check regular orders
        order = self.orders.get(order_id)
        if not order:
            return None

        price_levels = self.bids if order.side == OrderSide.BUY else self.asks
        if order.price in price_levels:
            removed_order = price_levels[order.price].remove_order(order_id)
            if removed_order:
                del self.orders[order_id]
                # Clean up empty price levels
                if not price_levels[order.price].orders:
                    del price_levels[order.price]
                    # Update best bid/ask if necessary
                    if order.side == OrderSide.BUY and self._best_bid and self._best_bid.price == order.price:
                        self._update_best_bid()
                    elif order.side == OrderSide.SELL and self._best_ask and self._best_ask.price == order.price:
                        self._update_best_ask()
                return removed_order
        return None

    def get_best_bid(self) -> Optional[PriceLevel]:
        """Get the best bid (highest price) as a PriceLevel object."""
        if not self.bids:
            return None
        best_price = max(self.bids.keys())
        return self.bids[best_price] if self.bids[best_price].orders else None

    def get_best_ask(self) -> Optional[PriceLevel]:
        """Get the best ask (lowest price) as a PriceLevel object."""
        if not self.asks:
            return None
        best_price = min(self.asks.keys())
        return self.asks[best_price] if self.asks[best_price].orders else None

    def get_best_bid_ask(self) -> Tuple[Optional[Decimal], Optional[Decimal]]:
        """Get the best bid and ask prices."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        return (
            best_bid.price if best_bid else None,
            best_ask.price if best_ask else None
        )

    def check_inactive_orders(self, current_price: Optional[Decimal] = None) -> List[Order]:
        """Check and activate any inactive orders that should be triggered."""
        activated_orders = []
        orders_to_remove = []

        for order_id, order in self.inactive_orders.items():
            if order.triggered:
                continue

            # Determine current price if not provided
            price_to_check = current_price
            if price_to_check is None:
                if order.side == OrderSide.SELL:
                    best_bid = self.get_best_bid()
                    price_to_check = best_bid.price if best_bid else None
                else:
                    best_ask = self.get_best_ask()
                    price_to_check = best_ask.price if best_ask else None
            if price_to_check is None:
                continue

            if order.order_type == OrderType.STOP_LOSS:
                if (order.side == OrderSide.SELL and price_to_check <= order.stop_price) or \
                   (order.side == OrderSide.BUY and price_to_check >= order.stop_price):
                    print("in here")
                    order.triggered = True
                    order.order_type = OrderType.MARKET
                    activated_orders.append(order)
                    orders_to_remove.append(order_id)

            elif order.order_type == OrderType.STOP_LIMIT:
                if (order.side == OrderSide.SELL and price_to_check <= order.stop_price) or \
                   (order.side == OrderSide.BUY and price_to_check >= order.stop_price):
                    order.triggered = True
                    order.order_type = OrderType.LIMIT
                    activated_orders.append(order)
                    orders_to_remove.append(order_id)

            elif order.order_type == OrderType.TAKE_PROFIT:
                if (order.side == OrderSide.SELL and price_to_check >= order.stop_price) or \
                   (order.side == OrderSide.BUY and price_to_check <= order.stop_price):
                    order.triggered = True
                    order.order_type = OrderType.MARKET
                    activated_orders.append(order)
                    orders_to_remove.append(order_id)

        # Remove triggered orders from inactive orders
        for order_id in orders_to_remove:
            del self.inactive_orders[order_id]

        return activated_orders

    def get_order_book_snapshot(self) -> dict:
        """Get a snapshot of the order book."""
        return {
            "symbol": self.symbol,
            "bids": [
                {
                    "price": str(price),
                    "quantity": str(level.total_quantity),
                    "orders": len(level.orders)
                }
                for price, level in sorted(self.bids.items(), reverse=True)
            ],
            "asks": [
                {
                    "price": str(price),
                    "quantity": str(level.total_quantity),
                    "orders": len(level.orders)
                }
                for price, level in sorted(self.asks.items())
            ],
            "timestamp": datetime.now(UTC).isoformat()
        }

    def _update_best_bid(self) -> None:
        """Update the best bid price level."""
        if not self.bids:
            self._best_bid = None
            return
        best_price = max(self.bids.keys())
        self._best_bid = self.bids[best_price]

    def _update_best_ask(self) -> None:
        """Update the best ask price level."""
        if not self.asks:
            self._best_ask = None
            return
        best_price = min(self.asks.keys())
        self._best_ask = self.asks[best_price]

    def update_order(self, order_id: str, new_quantity: Decimal) -> Optional[Order]:
        order = self.orders.get(order_id)
        if order:
            if order.side == OrderSide.BUY:
                price_level = self.bids[order.price]
                price_level.update_quantity(order_id, new_quantity)
                # Update best bid if this was the best price level
                if self._best_bid and self._best_bid.price == order.price:
                    if price_level.total_quantity > 0:
                        self._best_bid = price_level
                    else:
                        self._update_best_bid()
            else:
                price_level = self.asks[order.price]
                price_level.update_quantity(order_id, new_quantity)
                # Update best ask if this was the best price level
                if self._best_ask and self._best_ask.price == order.price:
                    if price_level.total_quantity > 0:
                        self._best_ask = price_level
                    else:
                        self._update_best_ask()
        return order

    def get_best_bid_quantity(self) -> Decimal:
        """Get the total quantity at the best bid price."""
        best_bid = self.get_best_bid()
        if not best_bid or not best_bid.orders:
            return Decimal('0')
        return best_bid.total_quantity

    def get_best_ask_quantity(self) -> Decimal:
        """Get the total quantity at the best ask price."""
        best_ask = self.get_best_ask()
        if not best_ask or not best_ask.orders:
            return Decimal('0')
        return best_ask.total_quantity

    def get_bbo(self) -> Dict:
        """Get the best bid and offer (BBO)."""
        best_bid = self.get_best_bid()
        best_ask = self.get_best_ask()
        
        return {
            "best_bid_price": float(best_bid.price) if best_bid else None,
            "best_bid_quantity": float(best_bid.total_quantity) if best_bid else None,
            "best_ask_price": float(best_ask.price) if best_ask else None,
            "best_ask_quantity": float(best_ask.total_quantity) if best_ask else None,
            "timestamp": datetime.utcnow().isoformat()
        }

    def get_pending_orders(self) -> Dict:
        """Get all pending orders in the order book."""
        pending_orders = {
            "bids": [],
            "asks": []
        }
        
        logger.debug(f"Retrieving pending orders for {self.symbol}")
        
        # Sort bids in descending order (highest price first)
        for price, level in sorted(self.bids.items(), reverse=True):
            if level.total_quantity > 0:
                for order in level.orders:
                    if order.status in ["OPEN", "PARTIALLY_FILLED"]:
                        pending_orders["bids"].append({
                            "order_id": order.id,
                            "price": str(price),
                            "quantity": str(order.quantity),
                            "filled_quantity": str(order.filled_quantity),
                            "status": order.status,
                            "timestamp": order.timestamp.isoformat()
                        })
                        logger.debug(f"Added order {order.id} to pending bids")
        
        # Sort asks in ascending order (lowest price first)
        for price, level in sorted(self.asks.items()):
            if level.total_quantity > 0:
                for order in level.orders:
                    if order.status in ["OPEN", "PARTIALLY_FILLED"]:
                        pending_orders["asks"].append({
                            "order_id": order.id,
                            "price": str(price),
                            "quantity": str(order.quantity),
                            "filled_quantity": str(order.filled_quantity),
                            "status": order.status,
                            "timestamp": order.timestamp.isoformat()
                        })
                        logger.debug(f"Added order {order.id} to pending asks")
        
        logger.debug(f"Pending orders retrieved: {pending_orders}")
        return pending_orders

    def get_top_levels(self, depth: int = 10) -> Dict:
        """Get top N levels of bids and asks.
        
        Args:
            depth: Number of price levels to return (default: 10)
            
        Returns:
            Dictionary containing arrays of [price, quantity] for bids and asks
        """
        result = {
            "bids": [],
            "asks": []
        }
        
        # Get top N bids (highest prices first)
        for price, level in sorted(self.bids.items(), reverse=True)[:depth]:
            if level.total_quantity > 0:
                result["bids"].append([str(price), str(level.total_quantity)])
        
        # Get top N asks (lowest prices first)
        for price, level in sorted(self.asks.items())[:depth]:
            if level.total_quantity > 0:
                result["asks"].append([str(price), str(level.total_quantity)])
        
        return result

    def match_order(self, order: Order) -> List[Trade]:
        """Match an order against the order book."""
        trades = []
        remaining_quantity = order.quantity

        if order.side == OrderSide.BUY:
            # Match against asks (sell orders)
            while remaining_quantity > 0 and self.asks:
                best_ask = self.get_best_ask()
                if not best_ask or not best_ask.orders:
                    break

                matching_order = best_ask.orders[0]
                
                # For limit orders, check if the prices cross
                if order.order_type != OrderType.MARKET and order.price is not None and order.price < matching_order.price:
                    break

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
                matching_order.filled_quantity = trade_quantity

                if matching_order.quantity == 0:
                    best_ask.remove_order(matching_order.id)
                    matching_order.status = "FILLED"
                    # Update best ask only if we removed an order
                    # self._update_best_ask()
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        else:  # SELL
            # Match against bids (buy orders)
            while remaining_quantity > 0 and self.bids:
                best_bid = self.get_best_bid()
                if not best_bid or not best_bid.orders:
                    break

                matching_order = best_bid.orders[0]
                
                # For limit orders, check if the prices cross
                if order.order_type != OrderType.MARKET and order.price is not None and order.price > matching_order.price:
                    break

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
                matching_order.filled_quantity = trade_quantity

                if matching_order.quantity == 0:
                    best_bid.remove_order(matching_order.id)
                    matching_order.status = "FILLED"
                    # Update best bid only if we removed an order
                    # self._update_best_bid()
                else:
                    matching_order.status = "PARTIALLY_FILLED"

        # Update the order's remaining quantity and status
        order.quantity = remaining_quantity
        order.filled_quantity = order.quantity - remaining_quantity

        if remaining_quantity == 0:
            order.status = "FILLED"
        elif order.filled_quantity > 0:
            order.status = "PARTIALLY_FILLED"
        else:
            order.status = "OPEN"

        # Only add the order to the book if it has remaining quantity
        # if remaining_quantity > 0:
        #     self.add_order(order)

        return trades

    def get_order_book_snapshot(self) -> dict:
        """Get a snapshot of the order book."""
        snapshot = {
            "symbol": self.symbol,
            "bids": [
                {
                    "price": str(price),
                    "quantity": str(level.total_quantity),
                    "orders": len(level.orders)
                }
                for price, level in sorted(self.bids.items(), reverse=True)
            ],
            "asks": [
                {
                    "price": str(price),
                    "quantity": str(level.total_quantity),
                    "orders": len(level.orders)
                }
                for price, level in sorted(self.asks.items())
            ],
            "timestamp": datetime.now(UTC).isoformat()
        }
        logger.debug(f"Retrieved order book snapshot for {self.symbol}: {snapshot}")
        return snapshot
