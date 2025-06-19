import httpx
import logging
from uuid import UUID

logger = logging.getLogger(__name__)

# ANALYTICS_SERVICE_URL = "http://analytics-service:5003/user/analytics/raw-data/{user_id}"
ANALYTICS_SERVICE_URL = "http://analytics-service:5003/user/analytics/raw-data"

async def fetch_user_analytics(user_id: UUID) -> dict:
    url = f"{ANALYTICS_SERVICE_URL}?user_id={user_id}&internal=true"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            logger.info(f"Fetched analytics data for user {user_id}: {data.get('analytics', {}).get('top_moods_from_history', 'No moods data found')}")
            return data
    except httpx.HTTPError as e:
        logger.error(f"[analytics-service] Ошибка при получении аналитики пользователя {user_id}: {e}")
        return {}