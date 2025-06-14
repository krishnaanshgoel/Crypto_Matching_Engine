import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')

# Matching Engine Configuration
MATCHING_ENGINE_CONFIG = {
    'redis_url': REDIS_URL,
    'log_level': 'INFO',
    'max_order_book_size': 1000,  # Maximum number of orders per price level
    'trade_history_size': 1000,   # Maximum number of trades to keep in history
} 