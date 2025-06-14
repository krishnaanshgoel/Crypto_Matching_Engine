import unittest
import asyncio
from decimal import Decimal
from datetime import datetime
from engine.base_models import Order, OrderSide, OrderType
from engine.matching_engine import MatchingEngine
from engine.order_book import OrderBook
import pytest
from uuid import uuid4

class TestMatchingEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MatchingEngine()
        self.symbol = "BTC-USD"
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    def test_market_order_matching(self):
        # Create a limit order first
        limit_order = Order(
            symbol=self.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal('1.0'),
            price=Decimal('50000.0')
        )
        
        # Create a market order to match against it
        market_order = Order(symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=Decimal('0.5'))
        
        # Add limit order to book
        self.engine.get_order_book(self.symbol).add_order(limit_order)
        
        # Process market order
        trades = self.loop.run_until_complete(self.engine.process_order(market_order))
        
        # Verify trade
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal('0.5'))
        self.assertEqual(trades[0].price, Decimal('50000.0'))

    def test_limit_order_matching(self):
        # Create two limit orders
        buy_order = Order(
            symbol=self.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal('1.0'),
            price=Decimal('50000.0')
        )
        
        sell_order = Order(
            symbol=self.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal('1.0'),
            price=Decimal('50000.0')
        )
        
        # Add buy order to book
        self.engine.get_order_book(self.symbol).add_order(buy_order)
        
        # Process sell order
        trades = self.loop.run_until_complete(self.engine.process_order(sell_order))
        
        # Verify trade
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal('1.0'))
        self.assertEqual(trades[0].price, Decimal('50000.0'))


    def test_ioc_order(self):
        # Create a limit order first
        limit_order = Order(
            symbol=self.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal('1.0'),
            price=Decimal('50000.0')
        )
        
        # Create an IOC order
        ioc_order = Order(
            symbol=self.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.IOC,
            quantity=Decimal('1.0'),
            price=Decimal('50000.0')
        )
        
        # Add limit order to book
        self.engine.get_order_book(self.symbol).add_order(limit_order)
        
        # Process IOC order
        trades = self.loop.run_until_complete(self.engine.process_order(ioc_order))
        
        # Verify trade
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].quantity, Decimal('1.0'))
        self.assertEqual(trades[0].price, Decimal('50000.0'))

    def test_fok_order(self):
        # Create a limit order first
        limit_order = Order(
            symbol=self.symbol,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=Decimal('0.5'),
            price=Decimal('50000.0')
        )
        
        # Create a FOK order
        fok_order = Order(
            symbol=self.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.FOK,
            quantity=Decimal('1.0'),
            price=Decimal('50000.0')
        )
        
        # Add limit order to book
        self.engine.get_order_book(self.symbol).add_order(limit_order)
        
        # Process FOK order
        trades = self.loop.run_until_complete(self.engine.process_order(fok_order))
        
        # Verify no trade (FOK should not execute if full quantity not available)
        self.assertEqual(len(trades), 0)


    def test_partial_fill_market_order(self):
       sell_order = Order(symbol=self.symbol, side=OrderSide.SELL, order_type=OrderType.LIMIT, quantity=Decimal('0.5'), price=Decimal('50000'))
       self.engine.get_order_book(self.symbol).add_order(sell_order)

       market_order = Order(symbol=self.symbol, side=OrderSide.BUY, order_type=OrderType.MARKET, quantity=Decimal('1.0'))
       trades = self.loop.run_until_complete(self.engine.process_order(market_order))

        # Verify trade
       self.assertEqual(len(trades), 1)
       self.assertEqual(trades[0].quantity, Decimal('0.5'))
       self.assertEqual(trades[0].price, Decimal('50000.0'))

@pytest.fixture
def matching_engine():
    return MatchingEngine()

@pytest.fixture
def sample_order():
    return Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

@pytest.fixture
def sample_market_order():
    return Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.0"),
        timestamp=datetime.utcnow()
    )

@pytest.fixture
def sample_stop_loss_order():
    return Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.STOP_LOSS,
        quantity=Decimal("1.0"),
        price=Decimal("45000.0"),
        stop_price=Decimal("45000.0"),
        timestamp=datetime.utcnow()
    )

@pytest.mark.asyncio
async def test_process_limit_order(matching_engine, sample_order):
    """Test processing a limit order."""
    trades = await matching_engine.process_order(sample_order)
    assert len(trades) == 0  # No matches initially
    assert sample_order.status == "OPEN"
    assert sample_order.quantity == Decimal("1.0")

@pytest.mark.asyncio
async def test_process_market_order(matching_engine, sample_market_order):
    """Test processing a market order."""
    trades = await matching_engine.process_order(sample_market_order)
    assert len(trades) == 0  # No matches initially
    assert sample_market_order.status == "FILLED"  # Market orders are filled or cancelled

@pytest.mark.asyncio
async def test_process_stop_loss_order(matching_engine, sample_stop_loss_order):
    """Test processing a stop loss order."""
    trades = await matching_engine.process_order(sample_stop_loss_order)
    assert len(trades) == 0  # No matches initially
    assert sample_stop_loss_order.status == "OPEN"

@pytest.mark.asyncio
async def test_matching_limit_orders(matching_engine):
    """Test matching two limit orders."""
    # Create a buy order
    buy_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Create a matching sell order
    sell_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Process buy order first
    trades1 = await matching_engine.process_order(buy_order)
    assert len(trades1) == 0
    assert buy_order.status == "OPEN"

    # Process sell order
    trades2 = await matching_engine.process_order(sell_order)
    assert len(trades2) == 1
    assert trades2[0].quantity == Decimal("1.0")
    assert trades2[0].price == Decimal("50000.0")
    assert buy_order.status == "FILLED"
    assert sell_order.status == "FILLED"

@pytest.mark.asyncio
async def test_matching_market_orders(matching_engine):
    """Test matching market orders with limit orders."""
    # Create a limit sell order
    sell_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Create a market buy order
    buy_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1.0"),
        timestamp=datetime.utcnow()
    )

    # Process sell order first
    trades1 = await matching_engine.process_order(sell_order)
    assert len(trades1) == 0
    assert sell_order.status == "OPEN"

    # Process buy order
    trades2 = await matching_engine.process_order(buy_order)
    assert len(trades2) == 1
    assert trades2[0].quantity == Decimal("1.0")
    assert trades2[0].price == Decimal("50000.0")
    assert sell_order.status == "FILLED"
    assert buy_order.status == "FILLED"

@pytest.mark.asyncio
async def test_stop_loss_activation(matching_engine):
    """Test stop loss order activation and execution."""
    # Create a stop loss order
    stop_loss = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.SELL,
        order_type=OrderType.STOP_LOSS,
        quantity=Decimal("1.0"),
        price=Decimal("45000.0"),
        stop_price=Decimal("45000.0"),
        timestamp=datetime.utcnow()
    )

    # Create a matching buy order
    buy_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("45000.0"),
        timestamp=datetime.utcnow()
    )

    # Process stop loss order first
    trades1 = await matching_engine.process_order(stop_loss)
    assert len(trades1) == 0
    assert stop_loss.status == "OPEN"

    # Process buy order to trigger stop loss
    trades2 = await matching_engine.process_order(buy_order)
    assert len(trades2) == 1
    assert trades2[0].quantity == Decimal("1.0")
    assert trades2[0].price == Decimal("45000.0")
    assert stop_loss.status == "FILLED"
    assert buy_order.status == "FILLED"

@pytest.mark.asyncio
async def test_fok_order_execution(matching_engine):
    """Test Fill-or-Kill order execution."""
    # Create a FOK order
    fok_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.FOK,
        quantity=Decimal("2.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Create two matching sell orders
    sell_order1 = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    sell_order2 = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Process sell orders first
    await matching_engine.process_order(sell_order1)
    await matching_engine.process_order(sell_order2)

    # Process FOK order
    trades = await matching_engine.process_order(fok_order)
    assert len(trades) == 2
    assert fok_order.status == "FILLED"
    assert sell_order1.status == "FILLED"
    assert sell_order2.status == "FILLED"

@pytest.mark.asyncio
async def test_ioc_order_execution(matching_engine):
    """Test Immediate-or-Cancel order execution."""
    # Create an IOC order
    ioc_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.BUY,
        order_type=OrderType.IOC,
        quantity=Decimal("2.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Create a matching sell order
    sell_order = Order(
        id=str(uuid4()),
        symbol="BTC_USD",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.0"),
        price=Decimal("50000.0"),
        timestamp=datetime.utcnow()
    )

    # Process sell order first
    await matching_engine.process_order(sell_order)

    # Process IOC order
    trades = await matching_engine.process_order(ioc_order)
    assert len(trades) == 1
    assert ioc_order.status == "FILLED"
    assert sell_order.status == "FILLED"
    assert ioc_order.quantity == Decimal("0.0")  # IOC orders are either filled or cancelled

if __name__ == '__main__':
    unittest.main() 