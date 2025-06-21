import uuid
from .broker.redis import redis_client, check_redis_connection


async def get_start_index(user_id: uuid.UUID) -> int:
    redis_connected = await check_redis_connection()
    if not redis_connected:
        print(f"[{user_id}] Redis connection failed. Cannot fetch recommendations.")
        return []

    key = f"{str(user_id)}_start_index"
    start_index = await redis_client.get(key)

    if start_index:
        print(f"Start index for user {user_id} found in Redis: {start_index}")
        try:
            return int(start_index)
        except (TypeError, ValueError):
            print(f"Invalid start_index value in Redis: {start_index}, defaulting to 0")
    else:
        print(f"No start index found for user {user_id}, defaulting to 0")

    return 0


async def save_start_index(user_id: uuid.UUID, index: int):
    redis_connected = await check_redis_connection()
    if not redis_connected:
        print(f"[{user_id}] Redis connection failed. Cannot fetch recommendations.")
        return []

    key = f"{str(user_id)}_start_index"

    if index < 0:
        index = 0

    await redis_client.set(key, index)
    print(f"Saved start index {index} for user {user_id} in Redis")
