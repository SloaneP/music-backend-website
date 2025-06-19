import logging
from fastapi import HTTPException
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from .broker.fetch_music_service import fetch_play_history_internal, fetch_favorites_internal
from .database import models
from .schemas import schemas
from .config import load_config
from .analyze import analyze_favorites, analyze_play_history

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

async def get_user_analytics(db: AsyncSession, user_id: UUID) -> models.UserAnalytics:
    result = await db.execute(
        select(models.UserAnalytics).where(models.UserAnalytics.user_id == user_id)
    )
    analytics = result.scalar_one_or_none()

    # Печатаем, что мы получили из базы данных
    if analytics:
        print(f"[DB] User analytics: {analytics}")
    else:
        print(f"[DB] No analytics found for user {user_id}")

    if not analytics:
        raise HTTPException(status_code=404, detail="Analytics not found")

    return analytics

async def upsert_user_analytics(
    db: AsyncSession, user_id: UUID, update_data: schemas.UserAnalyticsUpdate
) -> models.UserAnalytics:
    result = await db.execute(
        select(models.UserAnalytics).where(models.UserAnalytics.user_id == user_id)
    )
    analytics = result.scalar_one_or_none()

    if analytics:
        for field, value in update_data.dict(exclude_unset=True).items():
            setattr(analytics, field, value)
    else:
        analytics = models.UserAnalytics(
            user_id=user_id,
            **update_data.dict(exclude_unset=True)
        )
        db.add(analytics)

    await db.commit()
    await db.refresh(analytics)
    return analytics

async def update_user_analytics_in_db(
    db: AsyncSession, user_id: UUID, play_history: list, favorites: list
):
    play_history_analysis = analyze_play_history(play_history)
    favorites_analysis = analyze_favorites(favorites)

    update_data = schemas.UserAnalyticsUpdate(
        avg_duration_from_history=play_history_analysis['avg_duration'],
        avg_release_year_from_history=play_history_analysis['avg_release_year'],
        top_genres_from_history=play_history_analysis['top_genres'],
        top_moods_from_history=play_history_analysis['top_moods'],
        avg_duration_from_favorites=favorites_analysis['avg_duration'],
        avg_release_year_from_favorites=favorites_analysis['avg_release_year'],
        top_genres_from_favorites=favorites_analysis['top_genres'],
        top_moods_from_favorites=favorites_analysis['top_moods'],
        total_plays=play_history_analysis['total_tracks'],
        total_favorites=favorites_analysis.get('total_favorites', 0),
        most_favorite_tracks=favorites_analysis.get('top_favorites', [])
    )

    return await upsert_user_analytics(db, user_id, update_data)


async def get_and_update_user_analytics(
        db: AsyncSession,
        user_id: UUID,
        token: str | None = None,
        internal_call: bool = False,
):
    try:
        if internal_call:
            play_history = await fetch_play_history_internal(user_id)
            favorites = await fetch_favorites_internal(user_id)
        else:
            if not token:
                raise HTTPException(401, "Authorization token required")
            play_history = await fetch_play_history_internal(token)
            favorites = await fetch_favorites_internal(token)
    except httpx.HTTPStatusError as e:
        logger.error(f"Music service HTTP error: {e}")
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Music service error: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"Network error when contacting music service: {e}")
        raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")

    play_history_analysis = analyze_play_history(play_history)
    favorites_analysis = analyze_favorites(favorites)

    update_data = schemas.UserAnalyticsUpdate(
        avg_duration_from_history=play_history_analysis['avg_duration'],
        avg_release_year_from_history=play_history_analysis['avg_release_year'],
        top_genres_from_history=play_history_analysis['top_genres'],
        top_moods_from_history=play_history_analysis['top_moods'],
        avg_duration_from_favorites=favorites_analysis['avg_duration'],
        avg_release_year_from_favorites=favorites_analysis['avg_release_year'],
        top_genres_from_favorites=favorites_analysis['top_genres'],
        top_moods_from_favorites=favorites_analysis['top_moods'],
        total_plays=play_history_analysis['total_tracks'],
        total_favorites=favorites_analysis.get('total_favorites', 0),
        most_favorite_tracks=favorites_analysis.get('top_favorites', [])
    )

    analytics = await upsert_user_analytics(db, user_id, update_data)

    return {
        # "history": play_history,
        # "favorites": favorites,
        "analytics": analytics,
    }