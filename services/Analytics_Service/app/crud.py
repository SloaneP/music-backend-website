import logging
from collections import Counter
from fastapi import HTTPException
from uuid import UUID
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
import json
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

# async def create_play_event(db: AsyncSession, data: schemas.TrackPlayEventCreate) -> models.TrackPlayEvent:
#     new_event = models.TrackPlayEvent(**data.model_dump())
#     db.add(new_event)
#     await db.commit()
#     await db.refresh(new_event)
#     return new_event
#
# async def get_user_play_events(db: AsyncSession, user_id: UUID, limit: int = 100):
#     result = await db.execute(
#         select(models.TrackPlayEvent)
#         .where(models.TrackPlayEvent.user_id == user_id)
#         .order_by(models.TrackPlayEvent.played_at.desc())
#         .limit(limit)
#     )
#     return result.scalars().all()
#
# async def get_or_create_user_analytics(db: AsyncSession, user_id: UUID) -> models.UserAnalytics:
#     result = await db.execute(
#         select(models.UserAnalytics).where(models.UserAnalytics.user_id == user_id)
#     )
#     analytics = result.scalar_one_or_none()
#     if analytics is None:
#         analytics = models.UserAnalytics(user_id=user_id)
#         db.add(analytics)
#         await db.commit()
#         await db.refresh(analytics)
#     return analytics
#
# async def update_user_analytics(
#     db: AsyncSession,
#     user_id: UUID,
#     avg_duration: float,
#     avg_release_year: float,
#     top_genres: str,
#     top_artists: str
# ) -> models.UserAnalytics:
#     await db.execute(
#         update(models.UserAnalytics)
#         .where(models.UserAnalytics.user_id == user_id)
#         .values(
#             avg_duration=avg_duration,
#             avg_release_year=avg_release_year,
#             top_genres=top_genres,
#             top_artists=top_artists
#         )
#     )
#     await db.commit()
#
#     result = await db.execute(
#         select(models.UserAnalytics).where(models.UserAnalytics.user_id == user_id)
#     )
#     return result.scalar_one()
#
# async def get_user_analytics(db: AsyncSession, user_id: UUID) -> models.UserAnalytics | None:
#     result = await db.execute(
#         select(models.UserAnalytics).where(models.UserAnalytics.user_id == user_id)
#     )
#     return result.scalar_one_or_none()
#
# async def aggregate_user_profile(session, user_id: UUID):
#     events = await get_user_play_events(session, user_id, limit=1000)
#     if not events:
#         return
#
#     avg_duration = sum(e.played_duration for e in events) / len(events)
#     avg_year = sum(
#         getattr(e, "release_year", 0) or 0 for e in events
#     ) / len(events)
#
#     genres = [getattr(e, "genre", None) for e in events if getattr(e, "genre", None)]
#     artists = [getattr(e, "artist", None) for e in events if getattr(e, "artist", None)]
#
#     top_genres = ",".join([g for g, _ in Counter(genres).most_common(3)])
#     top_artists = ",".join([a for a, _ in Counter(artists).most_common(3)])
#
#     await get_or_create_user_analytics(session, user_id)
#     await update_user_analytics(
#         session,
#         user_id=user_id,
#         avg_duration=avg_duration,
#         avg_release_year=avg_year,
#         top_genres=top_genres,
#         top_artists=top_artists
#     )
