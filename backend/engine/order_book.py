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

    def __lt__(self, other):
        """Less than comparison for sorting."""
        return self.price < other.price

    def __gt__(self, other):
        """Greater than comparison for sorting."""
        return self.price > other.price

    def __eq__(self, other):
        """Equality comparison."""
        return self.price == other.price

    def add_order(self, order: Order) -> None:
        """Add an order to this price level."""
        self.orders.append(order)
        self.total_quantity += order.quantity

    def remove_order(self, order: Order) -> None:
        """Remove an order from this price level."""
        if order in self.orders:
            self.orders.remove(order)
            self.total_quantity -= order.quantity

    def dict(self) -> Dict:
        """Convert price level to dictionary format."""
        return {
            'price': str(self.price),
            'quantity': str(self.total_quantity),
            'orders': len(self.orders)
        }

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
        logger.info(f"Removing order {order_id} from order book")
        
        # Check bids
        for price, level in list(self.bids.items()):
            for order in level.orders:
                if order.id == order_id:
                    level.remove_order(order)
                    # Update best bid if we're removing from the best bid level
                    if self._best_bid and (self._best_bid.price == price or order in self._best_bid.orders):
                        logger.info(f"Removing order from best bid level at price {price}")
                        if not level.orders:
                            del self.bids[price]
                        self._update_best_bid()
                    # Remove empty price level
                    elif not level.orders:
                        del self.bids[price]
                    return order

        # Check asks
        for price, level in list(self.asks.items()):
            for order in level.orders:
                if order.id == order_id:
                    level.remove_order(order)
                    # Update best ask if we're removing from the best ask level
                    if self._best_ask and (self._best_ask.price == price or order in self._best_ask.orders):
                        logger.info(f"Removing order from best ask level at price {price}")
                        if not level.orders:
                            del self.asks[price]
                        self._update_best_ask()
                    # Remove empty price level
                    elif not level.orders:
                        del self.asks[price]
                    return order

        logger.warning(f"Order {order_id} not found in order book")
        return None

    def get_best_bid(self) -> Optional[PriceLevel]:
        """Get the best bid price level."""
        if not self._best_bid and self.bids:
            self._update_best_bid()
        return self._best_bid

    def get_best_ask(self) -> Optional[PriceLevel]:
        """Get the best ask price level."""
        if not self._best_ask and self.asks:
            self._update_best_ask()
        return self._best_ask

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
        """Update the best bid after order removal."""
        if not self.bids:
            self._best_bid = None
            logger.info("No bids left, best bid set to None")
            return

        # Find the highest price level with orders
        best_price = max(self.bids.keys())
        best_level = self.bids[best_price]
        
        if best_level.orders:
            self._best_bid = best_level
            logger.info(f"Updated best bid to price {best_price} with {len(best_level.orders)} orders and total quantity {best_level.total_quantity}")
        else:
            # If the best level is empty, remove it and try again
            del self.bids[best_price]
            logger.info(f"Removed empty bid level at price {best_price}")
            # Recursively find the next best bid
            self._update_best_bid()

    def _update_best_ask(self) -> None:
        """Update the best ask after order removal."""
        if not self.asks:
            self._best_ask = None
            logger.info("No asks left, best ask set to None")
            return

        # Find the lowest price level with orders
        best_price = min(self.asks.keys())
        best_level = self.asks[best_price]
        
        if best_level.orders:
            self._best_ask = best_level
            logger.info(f"Updated best ask to price {best_price} with {len(best_level.orders)} orders and total quantity {best_level.total_quantity}")
        else:
            # If the best level is empty, remove it and try again
            del self.asks[best_price]
            logger.info(f"Removed empty ask level at price {best_price}")
            # Recursively find the next best ask
            self._update_best_ask()

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
        """Get a snapshot of pending orders in the order book."""
        return {
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
                        for order in level.orders if order.status not in ["FILLED", "CANCELLED"]
                    ]
                }
                for level in sorted(self.bids.values(), key=lambda x: x.price, reverse=True)
                if any(order.status not in ["FILLED", "CANCELLED"] for order in level.orders)
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
                        for order in level.orders if order.status not in ["FILLED", "CANCELLED"]
                    ]
                }
                for level in sorted(self.asks.values(), key=lambda x: x.price)
                if any(order.status not in ["FILLED", "CANCELLED"] for order in level.orders)
            ],
            'timestamp': datetime.utcnow().isoformat()
        }

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
            while remaining_quantity > 0 and self.get_best_ask() and (order.price is not None and order.price >= self.get_best_ask().price or order.price==None):
                best_ask = self.get_best_ask()
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

                # Update quantities
                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity += trade_quantity

                # Update order status and handle removal
                if matching_order.quantity <= 0:
                    # Only remove if fully filled
                    best_ask.remove_order(matching_order)
                    matching_order.status = "FILLED"
                    # Update best ask if we removed the last order at this price
                    if not best_ask.orders:
                        del self.asks[best_ask.price]
                        self._update_best_ask()
                else:
                    # Keep partially filled order in the book
                    matching_order.status = "PARTIALLY_FILLED"
                    # Update best ask if we modified the quantity at this price
                    if best_ask.price == self._best_ask.price:
                        self._best_ask = best_ask
                        logger.info(f"Updated best ask quantity to {best_ask.total_quantity} at price {best_ask.price}")

        else:  # SELL
            while remaining_quantity > 0 and self.get_best_bid() and (order.price is not None and order.price <= self.get_best_bid().price or order.price==None):
                best_bid = self.get_best_bid()
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

                # Update quantities
                remaining_quantity -= trade_quantity
                matching_order.quantity -= trade_quantity
                matching_order.filled_quantity+= trade_quantity

                # Update order status and handle removal
                if matching_order.quantity <= 0:
                    # Only remove if fully filled
                    best_bid.remove_order(matching_order)
                    matching_order.status = "FILLED"
                    # Update best bid if we removed the last order at this price
                    if not best_bid.orders:
                        del self.bids[best_bid.price]
                        self._update_best_bid()
                else:
                    # Keep partially filled order in the book
                    matching_order.status = "PARTIALLY_FILLED"
                    # Update best bid if we modified the quantity at this price
                    if best_bid.price == self._best_bid.price:
                        self._best_bid = best_bid
                        logger.info(f"Updated best bid quantity to {best_bid.total_quantity} at price {best_bid.price}")

        # Update the incoming order's status
        if remaining_quantity > 0:
            order.quantity = remaining_quantity
            order.status = "PARTIALLY_FILLED"
        else:
            order.status = "FILLED"

        return trades

