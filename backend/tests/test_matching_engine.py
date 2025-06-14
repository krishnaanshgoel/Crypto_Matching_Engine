import unittest
import asyncio
from decimal import Decimal
from datetime import datetime
from engine.base_models import Order, OrderSide, OrderType
from engine.matching_engine import MatchingEngine
from engine.order_book import OrderBook

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


if __name__ == '__main__':
    unittest.main() 