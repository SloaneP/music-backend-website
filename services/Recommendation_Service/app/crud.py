import random

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Set
import logging

from .recommendation_service import save_start_index
from .schemas import UserRecommendationUpdate, TrackResponse
from .database.models import UserRecommendation
from .fetch_from_music_service.fetch_all_tracks import fetch_all_tracks_from_music_service
from .fetch_from_music_service.fetch_analytics import fetch_user_analytics
from .redis_recent import track_recent_key, push_recent_track_ids, MAX_RECENT
from .recommendation import recommend_tracks
from .broker.redis import redis_client
from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def get_recommended_tracks_from_db(db: AsyncSession, user_id: UUID) -> List[TrackResponse]:
    result = await db.execute(select(UserRecommendation).where(UserRecommendation.user_id == user_id))
    user_recommendation = result.scalars().first()

    if not user_recommendation:
        raise HTTPException(status_code=404, detail="Recommendations not found for this user")

    recommended_tracks = user_recommendation.recommended_tracks
    if not recommended_tracks:
        raise HTTPException(status_code=404, detail="No recommended tracks for this user")

    return [TrackResponse(id=str(track_id), title="Track Title", artist="Artist Name", track_url="Track URL", cover_url="Cover URL") for track_id in recommended_tracks]

async def get_recommendation_by_user_id(db: AsyncSession, user_id: UUID) -> UserRecommendation | None:
    result = await db.execute(
        select(UserRecommendation).where(UserRecommendation.user_id == user_id)
    )
    return result.scalars().first()

async def upsert_user_recommendation(db: AsyncSession, user_id: UUID, data: UserRecommendationUpdate) -> UserRecommendation:
    recommendation = await get_recommendation_by_user_id(db, user_id)
    if recommendation:
        for field, value in data.dict(exclude_unset=True).items():
            setattr(recommendation, field, value)
    else:
        recommendation = UserRecommendation(user_id=user_id, **data.dict())
        db.add(recommendation)
    await db.commit()
    await db.refresh(recommendation)
    return recommendation

# Получаем рекомендованные треки
async def get_recommended_tracks(db: AsyncSession, user_id: UUID) -> List[TrackResponse]:
    recent_key = track_recent_key(user_id)

    try:
        recent_ids_list = await redis_client.lrange(recent_key, 0, MAX_RECENT - 1)
        recent_ids: Set[str] = set(recent_ids_list)
    except Exception as e:
        logger.error(f"[{user_id}] Redis error: {e}")
        recent_ids = set()

    logger.info(f"[{user_id}] Recent IDs count: {len(recent_ids)}")

    analytics = await fetch_user_analytics(user_id)
    if not analytics:
        logger.error(f"[{user_id}] No analytics data found")
        return []

    all_tracks = await fetch_all_tracks_from_music_service()
    logger.info(f"[{user_id}] Total tracks fetched: {len(all_tracks)}")

    if not all_tracks:
        return []

    all_ids = {str(t["id"]) for t in all_tracks}

    if recent_ids.issuperset(all_ids):
        logger.info(f"[{user_id}] Recent IDs cover all tracks, resetting recent history")
        await redis_client.delete(recent_key)
        recent_ids = set()

    filtered_tracks = [t for t in all_tracks if str(t["id"]) not in recent_ids]

    if len(filtered_tracks) < 6:
        logger.info(f"[{user_id}] Not enough filtered tracks, resetting recent history")
        filtered_tracks = all_tracks

    selected = await recommend_tracks(user_id, analytics, filtered_tracks, recent_ids)

    recommended_tracks_details = [
        TrackResponse(
            id=str(t["id"]),
            title=t.get("title", ""),
            artist=t.get("artist", ""),
            track_url=t.get("track_url", ""),
            cover_url=t.get("cover_url", "")
        ) for t in selected
    ]

    update_data = UserRecommendationUpdate(
        recommended_tracks=[t.id for t in recommended_tracks_details],
        avg_duration_from_history=analytics.get('avg_duration_from_history', None),
        avg_release_year_from_history=analytics.get('avg_release_year_from_history', None),
        top_genres_from_history=analytics.get('top_genres_from_history', None),
        top_moods_from_history=analytics.get('top_moods_from_history', None),
        avg_duration_from_favorites=analytics.get('avg_duration_from_favorites', None),
        avg_release_year_from_favorites=analytics.get('avg_release_year_from_favorites', None),
        top_genres_from_favorites=analytics.get('top_genres_from_favorites', None),
        top_moods_from_favorites=analytics.get('top_moods_from_favorites', None),
        total_plays=analytics.get('total_plays', None),
        total_favorites=analytics.get('total_favorites', None),
        most_favorite_tracks=analytics.get('most_favorite_tracks', []),
    )

    await upsert_user_recommendation(db, user_id, update_data)
    await push_recent_track_ids(redis_client, user_id, [t["id"] for t in selected if t.get("id")])

    return recommended_tracks_details