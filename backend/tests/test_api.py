import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from api.main import app
from engine.base_models import OrderSide, OrderType

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def symbol():
    return "BTC-USD"

def test_create_market_order(client, symbol):
    # Test creating a market order
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "1.0"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["side"] == "BUY"
    assert data["order_type"] == "MARKET"
    assert data["quantity"] == "1.0"

# def test_create_limit_order(client, symbol):
#     # Test creating a limit order
#     response = client.post(
#         "/orders",
#         json={
#             "symbol": symbol,
#             "side": "SELL",
#             "order_type": "LIMIT",
#             "quantity": "1.0",
#             "price": "50000.0"
#         }
#     )

#     # Print response content if status code is not 200
#     if response.status_code != 200:
#         print(f"Error response: {response.content}")

#     # Verify response
#     assert response.status_code == 200
#     data = response.json()
#     assert data["symbol"] == symbol
#     assert data["side"] == "SELL"
#     assert data["order_type"] == "LIMIT"
#     assert data["quantity"] == "1.0"
#     assert data["price"] == "50000.0"

def test_create_stop_loss_order(client, symbol):
    # Test creating a stop loss order
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "SELL",
            "order_type": "STOP_LOSS",
            "quantity": "1.0",
            "stop_price": "45000.0"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["side"] == "SELL"
    assert data["order_type"] == "STOP_LOSS"
    assert data["quantity"] == "1.0"
    assert data["stop_price"] == "45000.0"

def test_create_stop_limit_order(client, symbol):
    # Test creating a stop limit order
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "SELL",
            "order_type": "STOP_LIMIT",
            "quantity": "1.0",
            "price": "45000.0",
            "stop_price": "46000.0"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["side"] == "SELL"
    assert data["order_type"] == "STOP_LIMIT"
    assert data["quantity"] == "1.0"
    assert data["price"] == "45000.0"
    assert data["stop_price"] == "46000.0"

def test_create_take_profit_order(client, symbol):
    # Test creating a take profit order
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "SELL",
            "order_type": "TAKE_PROFIT",
            "quantity": "1.0",
            "stop_price": "55000.0"
        }
    )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == symbol
    assert data["side"] == "SELL"
    assert data["order_type"] == "TAKE_PROFIT"
    assert data["quantity"] == "1.0"
    assert data["stop_price"] == "55000.0"

def test_invalid_order_type(client, symbol):
    # Test creating an order with invalid order type
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "BUY",
            "order_type": "INVALID",
            "quantity": "1.0"
        }
    )
    
    # Verify response
    assert response.status_code == 422

def test_missing_required_fields(client, symbol):
    # Test creating an order with missing required fields
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "BUY"
        }
    )
    
    # Verify response
    assert response.status_code == 422

def test_invalid_quantity(client, symbol):
    # Test creating an order with invalid quantity
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "-1.0"
        }
    )
    
    # Verify response
    assert response.status_code == 422

def test_invalid_price(client, symbol):
    # Test creating a limit order with invalid price
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": "1.0",
            "price": "-50000.0"
        }
    )
    
    # Verify response
    assert response.status_code == 422

def test_invalid_stop_price(client, symbol):
    # Test creating a stop loss order with invalid stop price
    response = client.post(
        "/orders",
        json={
            "symbol": symbol,
            "side": "SELL",
            "order_type": "STOP_LOSS",
            "quantity": "1.0",
            "stop_price": "-45000.0"
        }
    )
    
    # Verify response
    assert response.status_code == 422 