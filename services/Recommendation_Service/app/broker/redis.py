import redis.asyncio as redis
from redis.exceptions import RedisError


redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

async def check_redis_connection():
    try:
        await redis_client.ping()
        print("[cache] Redis is connected")
    except RedisError as e:
        print(f"[cache] Redis connection error: {e}")
        return False
    return True