from uuid import UUID
from typing import List
import logging

from .broker.redis import check_redis_connection

logger = logging.getLogger(__name__)
MAX_RECENT = 100


def track_recent_key(user_id: UUID) -> str:
    return f"user:{user_id}:recent_tracks"


async def push_recent_track_ids(redis_client, user_id: UUID, track_ids: List[str]):
    redis_connected = await check_redis_connection()
    if not redis_connected:
        print(f"[{user_id}] Redis connection failed. Cannot fetch recommendations.")
        return []

    if not track_ids:
        logger.warning(f"[{user_id}] No track IDs provided to update recent track history.")
        return

    key = track_recent_key(user_id)

    try:
        for tid in track_ids:
            if await redis_client.lrem(key, 0, tid) == 0:
                await redis_client.lpush(key, tid)

        await redis_client.ltrim(key, 0, MAX_RECENT - 1)

        logger.info(f"[{user_id}] Updated recent track history in Redis with {len(track_ids)} tracks.")

    except Exception as e:
        logger.error(f"[{user_id}] Error while updating recent track history in Redis: {e}")

# async def push_recent_track_ids(redis_client, user_id: UUID, track_ids: List[str]):
#     key = track_recent_key(user_id)
#     for tid in track_ids:
#         await redis_client.lpush(key, tid)
#     await redis_client.ltrim(key, 0, MAX_RECENT - 1)
