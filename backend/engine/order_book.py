from decimal import Decimal
from typing import Dict, List, Optional
from collections import defaultdict
from datetime import datetime

from engine.base_models import Order, OrderSide

class PriceLevel:
    def __init__(self, price: Decimal):
        self.price = price
        self.orders: List[Order] = []
        self.total_quantity = Decimal('0')

    def add_order(self, order: Order) -> None:
        self.orders.append(order)
        self.total_quantity += order.quantity

    def remove_order(self, order: Order) -> None:
        if order in self.orders:
            self.orders.remove(order)
            self.total_quantity -= order.quantity

    def update_order(self, order: Order, new_quantity: Decimal) -> None:
        if order in self.orders:
            old_quantity = order.quantity
            order.quantity = new_quantity
            self.total_quantity = self.total_quantity - old_quantity + new_quantity

class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.bids: Dict[Decimal, PriceLevel] = {}
        self.asks: Dict[Decimal, PriceLevel] = {}
        self.orders: Dict[str, Order] = {}
        self._best_bid: Optional[PriceLevel] = None
        self._best_ask: Optional[PriceLevel] = None

    def add_order(self, order: Order) -> None:
        self.orders[order.id] = order
        if order.side == OrderSide.BUY:
            if order.price not in self.bids:
                self.bids[order.price] = PriceLevel(order.price)
            self.bids[order.price].add_order(order)
            if self._best_bid is None or order.price > self._best_bid.price:
                self._best_bid = self.bids[order.price]
        else:
            if order.price not in self.asks:
                self.asks[order.price] = PriceLevel(order.price)
            self.asks[order.price].add_order(order)
            if self._best_ask is None or order.price < self._best_ask.price:
                self._best_ask = self.asks[order.price]

    def remove_order(self, order: Order) -> None:
        """Remove an order from the book."""
        if order.side == OrderSide.BUY:
            price_level = self.bids.get(order.price)
            if price_level:
                price_level.remove_order(order)
                if not price_level.orders:
                    del self.bids[order.price]
                # Always update best bid after removal
                self._update_best_bid()
        else:
            price_level = self.asks.get(order.price)
            if price_level:
                price_level.remove_order(order)
                if not price_level.orders:
                    del self.asks[order.price]
                # Always update best ask after removal
                self._update_best_ask()

    def _update_best_bid(self) -> None:
        """Update the best bid price level."""
        if not self.bids:
            self._best_bid = None
            return
            
        # Find the highest price with non-empty orders
        best_price = None
        for price in sorted(self.bids.keys(), reverse=True):
            level = self.bids[price]
            if level.orders and level.total_quantity > 0:
                best_price = price
                break
                
        if best_price is not None:
            self._best_bid = self.bids[best_price]
        else:
            self._best_bid = None

    def _update_best_ask(self) -> None:
        """Update the best ask price level."""
        if not self.asks:
            self._best_ask = None
            return
            
        # Find the lowest price with non-empty orders
        best_price = None
        for price in sorted(self.asks.keys()):
            level = self.asks[price]
            if level.orders and level.total_quantity > 0:
                best_price = price
                break
                
        if best_price is not None:
            self._best_ask = self.asks[best_price]
        else:
            self._best_ask = None

    def update_order(self, order_id: str, new_quantity: Decimal) -> Optional[Order]:
        order = self.orders.get(order_id)
        if order:
            if order.side == OrderSide.BUY:
                price_level = self.bids[order.price]
                price_level.update_order(order, new_quantity)
                # Update best bid if this was the best price level
                if self._best_bid and self._best_bid.price == order.price:
                    if price_level.total_quantity > 0:
                        self._best_bid = price_level
                    else:
                        self._update_best_bid()
            else:
                price_level = self.asks[order.price]
                price_level.update_order(order, new_quantity)
                # Update best ask if this was the best price level
                if self._best_ask and self._best_ask.price == order.price:
                    if price_level.total_quantity > 0:
                        self._best_ask = price_level
                    else:
                        self._update_best_ask()
        return order

    def get_best_bid(self) -> Optional[PriceLevel]:
        """Get the best bid price level."""
        if not self._best_bid or not self._best_bid.orders or self._best_bid.total_quantity <= 0:
            self._update_best_bid()
        return self._best_bid

    def get_best_ask(self) -> Optional[PriceLevel]:
        """Get the best ask price level."""
        if not self._best_ask or not self._best_ask.orders or self._best_ask.total_quantity <= 0:
            self._update_best_ask()
        return self._best_ask

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
        
        # Sort bids in descending order (highest price first)
        for price, level in sorted(self.bids.items(), reverse=True):
            if level.total_quantity > 0:
                for order in level.orders:
                    if order.status in ["NEW", "PARTIALLY_FILLED"]:
                        pending_orders["bids"].append({
                            "order_id": order.id,
                            "price": str(price),
                            "quantity": str(order.quantity),
                            "filled_quantity": str(order.filled_quantity),
                            "status": order.status,
                            "timestamp": order.timestamp.isoformat()
                        })
        
        # Sort asks in ascending order (lowest price first)
        for price, level in sorted(self.asks.items()):
            if level.total_quantity > 0:
                for order in level.orders:
                    if order.status in ["NEW", "PARTIALLY_FILLED"]:
                        pending_orders["asks"].append({
                            "order_id": order.id,
                            "price": str(price),
                            "quantity": str(order.quantity),
                            "filled_quantity": str(order.filled_quantity),
                            "status": order.status,
                            "timestamp": order.timestamp.isoformat()
                        })
        
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
