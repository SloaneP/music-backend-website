from typing import Optional
from fastapi import Query
import httpx
import logging
import json
from redis.asyncio import Redis
from redis.exceptions import RedisError


MUSIC_SERVICE_URL = "http://music-service:5002/tracks"

async def get_my_wave(mood: Optional[str] = Query(None)):
    params = {"mood": mood} if mood else {}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MUSIC_SERVICE_URL}/tracks", params=params)
        response.raise_for_status()
        return response.json()