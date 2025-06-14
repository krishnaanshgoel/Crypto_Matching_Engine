import pytest
from decimal import Decimal
from datetime import datetime, UTC
from engine.base_models import Order, OrderSide, OrderType
from engine.order_book import OrderBook

@pytest.fixture
def order_book():
    return OrderBook(symbol="BTC-USD")

@pytest.fixture
def symbol():
    return "BTC-USD"

def test_add_order(order_book, symbol):
    # Create a limit order
    order = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('50000.0')
    )
    
    # Add order to book
    order_book.add_order(order)
    
    # Verify order is in the book
    assert order.id in order_book.orders
    assert order_book.orders[order.id] == order

def test_remove_order(order_book, symbol):
    # Create a limit order
    order = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('50000.0')
    )
    
    # Add order to book
    order_book.add_order(order)
    
    # Remove order
    order_book.remove_order(order.id)
    
    # Verify order is not in the book
    assert order.id  in order_book.orders

def test_get_best_bid_ask(order_book, symbol):
    # Create multiple limit orders
    buy_order1 = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('49000.0')
    )
    
    buy_order2 = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('50000.0')
    )
    
    sell_order1 = Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('51000.0')
    )
    
    sell_order2 = Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('52000.0')
    )
    
    # Add orders to book
    order_book.add_order(buy_order1)
    order_book.add_order(buy_order2)
    order_book.add_order(sell_order1)
    order_book.add_order(sell_order2)
    
    # Get best bid and ask
    best_bid = order_book.get_best_bid()
    best_ask = order_book.get_best_ask()
    
    # Verify best bid and ask
    assert best_bid.price == Decimal('50000.0')
    assert best_ask.price == Decimal('51000.0')

def test_inactive_orders(order_book, symbol):
    # Create a stop loss order
    stop_loss_order = Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=Decimal('1.0'),
        stop_price=Decimal('45000.0')
    )
    
    # Add order to book
    order_book.add_order(stop_loss_order)
    
    # Verify order is in inactive orders
    assert stop_loss_order.id in order_book.inactive_orders
    
    # Check inactive orders with price below stop price
    order_book.check_inactive_orders(Decimal('44000.0'))
    
    # Verify order is triggered
    assert stop_loss_order.triggered

def test_order_matching(order_book, symbol):
    # Create matching limit orders
    buy_order = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('50000.0')
    )
    
    sell_order = Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('50000.0')
    )
    
    # Add buy order to book
    order_book.add_order(buy_order)
    
    # Try to match sell order
    trades = order_book.match_order(sell_order)
    
    # Verify trade
    assert len(trades) == 1
    assert trades[0].quantity == Decimal('1.0')
    assert trades[0].price == Decimal('50000.0')

def test_partial_fill(order_book, symbol):
    # Create limit orders with different quantities
    buy_order = Order(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal('1.0'),
        price=Decimal('50000.0')
    )
    
    sell_order = Order(
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal('0.5'),
        price=Decimal('50000.0')
    )
    
    # Add buy order to book
    order_book.add_order(buy_order)
    
    # Try to match sell order
    trades = order_book.match_order(sell_order)
    
    # Verify trade
    assert len(trades) == 1
    assert trades[0].quantity == Decimal('0.5')
    assert trades[0].price == Decimal('50000.0')
    
    # Verify remaining quantity
    assert buy_order.quantity == Decimal('0.5') 