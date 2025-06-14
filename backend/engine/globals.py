import os
from engine.matching_engine import MatchingEngine
from config import MATCHING_ENGINE_CONFIG

# Get Redis URL from environment or use default
redis_url = os.getenv('REDIS_URL', MATCHING_ENGINE_CONFIG['redis_url'])

# Initialize matching engine with Redis
matching_engine = MatchingEngine(redis_url=redis_url) 