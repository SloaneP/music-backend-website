import os
import httpx
from typing import List
from uuid import UUID

MUSIC_SERVICE_URL = os.getenv("MUSIC_SERVICE_URL", "http://music-service:5002")

async def fetch_play_history_internal(user_id: UUID, offset: int = 0) -> List[dict]:
    try:
        async with httpx.AsyncClient() as client:
            url = f"{MUSIC_SERVICE_URL}/internal/history/{user_id}?offset={offset}"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as e:
        print(f"An error occurred while requesting internal play history: {e}")
        raise
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}")
        raise

async def fetch_favorites_internal(user_id: UUID) -> List[dict]:
    try:
        async with httpx.AsyncClient() as client:
            url = f"{MUSIC_SERVICE_URL}/internal/favorites/{user_id}"
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as e:
        print(f"An error occurred while requesting internal favorites: {e}")
        raise
    except httpx.HTTPStatusError as e:
        print(f"HTTP error occurred: {e}")
        raise
