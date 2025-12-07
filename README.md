# GoQuant - High-Performance Trading Engine
#[Demo video](https://youtu.be/tU6jc6rTOTE).

A high-performance, real-time trading engine built with FastAPI, WebSocket support, and Redis persistence. This project implements a complete order matching engine with support for various order types, real-time market data, and comprehensive logging.

## Features

### Order Types
- **Limit Orders**: Orders executed at a specific price or better
- **Market Orders**: Orders executed at the best available price
- **Stop Loss Orders**: Orders triggered when price reaches a specified level
- **Stop Limit Orders**: Limit orders triggered by a stop price
- **Take Profit Orders**: Orders triggered when price reaches a profit target
- **IOC (Immediate-or-Cancel)**: Orders that must be filled immediately or cancelled
- **FOK (Fill-or-Kill)**: Orders that must be filled completely or cancelled

### Real-time Market Data
- WebSocket-based real-time updates
- Best Bid/Offer (BBO) streaming
- Trade execution notifications
- Order book updates
- Price level updates

### Order Book Management
- Price-time priority matching
- Partial order fills
- Order cancellation
- Price level management
- Quantity tracking
- BBO updates

### Persistence
- Redis-based order book persistence
- Trade history storage
- Order state management
- Recovery mechanisms

### API Endpoints

#### REST Endpoints

1. **Order Management**
   ```
   POST /api/v1/orders
   ```
   - Create new orders
   - Supports all order types
   - Returns order status and execution details

   ```
   GET /api/v1/orders/{order_id}
   ```
   - Get order details
   - Returns order status, fills, and execution details

   ```
   DELETE /api/v1/orders/{order_id}
   ```
   - Cancel existing orders
   - Returns cancellation status

2. **Market Data**
   ```
   GET /api/v1/pending-orders/{symbol}
   ```
   - Get current order book state
   - Returns all pending orders

   ```
   GET /api/v1/trades/{symbol}
   ```
   - Get trade history
   - Returns executed trades

   ```
   GET /api/v1/bbo/{symbol}
   ```
   - Get current Best Bid/Offer
   - Returns price and quantity information

#### WebSocket Endpoints

1. **Market Data Stream**
   ```
   ws://localhost:8000/ws/pending-orders/{symbol}
   ```
   - Real-time order book updates
   - BBO changes
   - Price level updates

2. **Trade Stream**
   ```
   ws://localhost:8000/ws/trades/{symbol}
   ```
   - Real-time trade execution notifications
   - Trade details and execution prices

3. **Order Updates**
   ```
   ws://localhost:8000/ws/orders/{symbol}
   ```
   - Real-time order status updates
   - Order execution details
   - Partial fill notifications

### Order Matching Logic

1. **Price-Time Priority**
   - Orders are matched based on price and time priority
   - Best price orders are matched first
   - Earlier orders at the same price are matched first

2. **Partial Fills**
   - Orders can be partially filled
   - Remaining quantity stays in the order book
   - BBO updates with remaining quantities

3. **Order Types**
   - Market orders match against best available price
   - Limit orders match if price conditions are met
   - Stop orders are triggered at specified prices
   - IOC/FOK orders have immediate execution requirements

### Logging System

1. **Application Logs**
   - Order processing logs
   - Trade execution logs
   - Error and exception logs
   - Performance metrics

2. **Market Data Logs**
   - Order book changes
   - BBO updates
   - Trade executions
   - Price level updates

3. **System Logs**
   - Redis connection logs
   - WebSocket connection logs
   - API request logs
   - Error tracking

### Unit Tests

1. **Order Book Tests**
   - Order addition/removal
   - Order matching
   - Price level management
   - BBO updates

2. **Matching Engine Tests**
   - Order type handling
   - Trade execution
   - Partial fills
   - Order cancellation

3. **API Tests**
   - Endpoint functionality
   - Request validation
   - Response formatting
   - Error handling

4. **WebSocket Tests**
   - Connection handling
   - Data streaming
   - Real-time updates
   - Error recovery

### Performance Features

1. **Concurrent Processing**
   - Asynchronous order processing
   - Thread pool for CPU-intensive tasks
   - Non-blocking I/O operations

2. **Caching**
   - Order book caching
   - BBO caching
   - Redis caching

3. **Optimization**
   - Efficient data structures
   - Minimal memory usage
   - Fast order matching
   - Quick BBO updates

### Error Handling

1. **Validation**
   - Order validation
   - Price validation
   - Quantity validation
   - Symbol validation

2. **Recovery**
   - Redis connection recovery
   - WebSocket reconnection
   - Order book recovery
   - State consistency checks

### Security

1. **Input Validation**
   - Order validation
   - Price/quantity validation
   - Symbol validation
   - Request validation

2. **Error Prevention**
   - Duplicate order prevention
   - Invalid state prevention
   - Race condition handling
   - Data consistency checks

## Setup and Installation

1. **Prerequisites**
   ```bash
   Python 3.8+
   Redis Server
   ```

2. **Installation**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configuration**
   - Set up Redis connection
   - Configure logging
   - Set up WebSocket endpoints
   - Configure API settings

4. **Running the Application**
   ```bash
   uvicorn main:app --reload
   ```

## Project Structure

```
backend/
├── api/
│   ├── endpoints/
│   ├── models/
│   └── websocket/
├── engine/
│   ├── order_book.py
│   ├── matching_engine.py
│   └── models.py
├── utils/
│   ├── logging.py
│   └── redis.py
└── tests/
    ├── test_order_book.py
    ├── test_matching_engine.py
    └── test_api.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- FastAPI for the web framework
- Redis for persistence
- WebSocket for real-time updates
- Python for the programming language 
