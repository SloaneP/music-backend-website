import uuid
from .broker.redis import redis_client


async def get_start_index(user_id: uuid.UUID) -> int:
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
    key = f"{str(user_id)}_start_index"

    if index < 0:
        index = 0  # защита от отрицательных индексов

    await redis_client.set(key, index)
    print(f"Saved start index {index} for user {user_id} in Redis")
