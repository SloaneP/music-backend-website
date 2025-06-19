import logging
from .celery_worker import celery_app
import redis
import httpx
import asyncio

from ...config import load_config

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

r = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)

def get_active_user_ids() -> list[str]:
    active_users = r.smembers("active_users")
    return list(active_users)

@celery_app.task(name="tasks.update_user_analytics_for_all")
def update_user_analytics_for_all():
    async def _update():
        active_user_ids = get_active_user_ids()
        logger.info(f"Found {len(active_user_ids)} active users to update analytics.")

        async with httpx.AsyncClient() as client:
            for user_id in active_user_ids:
                try:
                    url = f"http://analytics-service:5003/user/analytics/raw-data"
                    params = {"user_id": str(user_id), "internal": "true"}
                    logger.info(f"Requesting analytics for user {user_id} at {url} with params {params}")
                    response = await client.get(url, params=params)
                    response.raise_for_status()
                    logger.info(f"Analytics updated for user {user_id}, response status: {response.status_code}")
                except Exception as e:
                    logger.error(f"Failed to update analytics for user {user_id}: {e}")

    asyncio.run(_update())