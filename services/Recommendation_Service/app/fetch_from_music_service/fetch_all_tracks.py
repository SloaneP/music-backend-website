import httpx
import logging
import json
from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

MUSIC_SERVICE_URL = "http://music-service:5002/tracks"
CACHE_KEY = "cached_all_tracks"
CACHE_TTL = 300

redis_client = Redis(host="redis", port=6379, db=0, decode_responses=True)

async def update_tracks_in_redis(all_tracks):
    try:
        cached_tracks_data = await redis_client.get(CACHE_KEY)
        if cached_tracks_data:
            cached_tracks = json.loads(cached_tracks_data)
        else:
            cached_tracks = []

        track_ids_in_cache = {track["id"] for track in cached_tracks}

        for track in all_tracks:
            track_id = track["id"]
            track_version = track.get("updated_at", "default")

            if track_id in track_ids_in_cache:
                for cached_track in cached_tracks:
                    if cached_track["id"] == track_id and cached_track.get("updated_at") != track_version:
                        cached_tracks.remove(cached_track)
                        cached_tracks.append(track)
                        logger.info(f"[cache] Track {track_id} updated in cache.")
                        break
            else:
                cached_tracks.append(track)

        await redis_client.set(CACHE_KEY, json.dumps(cached_tracks), ex=CACHE_TTL)
        logger.info(f"[cache] Saved {len(cached_tracks)} tracks in Redis.")

    except RedisError as e:
        logger.warning(f"[cache] Failed to update Redis: {e}")
    except Exception as e:
        logger.error(f"[cache] Unexpected error: {e}")


async def fetch_all_tracks_from_music_service(limit_per_page: int = 100) -> list[dict]:
    try:
        cached = await redis_client.get(CACHE_KEY)
        if cached:
            logger.info(f"[cache] Loaded from Redis: {CACHE_KEY}")
            return json.loads(cached)
    except RedisError as e:
        logger.warning(f"[cache] Redis unavailable during get: {e}")

    logger.info("[cache] Cache is empty or Redis is unavailable — fetching from music-service.")
    all_tracks = []
    skip = 0

    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params = {"skip": skip, "limit": limit_per_page}
            try:
                response = await client.get(MUSIC_SERVICE_URL, params=params)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(f"[music-service] HTTP {e.response.status_code}: {e}")
                break
            except httpx.RequestError as e:
                logger.error(f"[music-service] Request failed: {e}")
                break

            tracks = response.json()
            if not tracks:
                break

            all_tracks.extend(tracks)
            skip += limit_per_page

    try:
        await update_tracks_in_redis(all_tracks)
    except RedisError as e:
        logger.warning(f"[cache] Failed to save in Redis: {e}")

    return all_tracks
