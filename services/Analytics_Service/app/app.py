import asyncio
import logging
from uuid import UUID
from typing import Optional

import jwt
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from . import config, crud, schemas
from .database import db_initializer, get_async_session
from .config import load_config

from collections import Counter
from sqlalchemy import select
from .broker.rabbitmq_producer import send_track_play_event
from .broker.rabbitmq_consumer import consume_track_play_events

from .broker.fetch_music_service import fetch_favorites, fetch_play_history

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

app = FastAPI(
    title=cfg.SERVICE_NAME,
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    try:
        await db_initializer.init_db(str(cfg.PG_ASYNC_DSN))
        logger.info("Database initialized successfully.")
        logger.info(f"Async session maker: {db_initializer.async_session_maker}")
    except Exception as e:
        logger.exception("Failed to initialize database: %s", e)


# ─────────── TOKEN ─────────── #
def extract_email_data(token: str) -> Optional[tuple[str, UUID]]:
    logger.info(f"Decoding token: {token}")
    try:
        data = jwt.decode(
            token,
            cfg.JWT_SECRET,
            algorithms=["HS256"],
            audience=["fastapi-users:auth"]
        )
        logger.info(f"Token decoded successfully: {data}")

        email = data.get("email")
        user_id = data.get("sub")

        logger.info(f"Extracted email: {email}, user_id: {user_id}")
        if email and user_id:
            return email, UUID(user_id)

    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while decoding token: {e}")

    logger.warning("Returning None from extract_email_data")
    return None

async def get_current_user(request: Request) -> tuple[str, UUID] | None:
    auth_header = request.headers.get("authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    user_data = extract_email_data(token)

    if not user_data:
        logger.warning("Invalid or expired token")
        return None

    email, user_id = user_data
    return email, user_id

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

# ─────────── FETCH DATA FROM MUSIC_SERVICE ROUTES ─────────── #
@app.get("/user/analytics/raw-data")
async def get_raw_data(request: Request, db: AsyncSession = Depends(get_async_session)):
    token = request.headers.get("authorization")

    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = token.split(" ")[1]
    user_data = extract_email_data(token)

    if not user_data:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    email, user_id = user_data
    logger.info(f"Extracted email: {email}, user_id: {user_id}")

    try:
        play_history = await fetch_play_history(token)
        favorites = await fetch_favorites(token)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"Music service error: {e.response.text}"
        )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")

    await crud.update_user_analytics_in_db(db, user_id, play_history, favorites)

    return {
        "history": play_history,
        "favorites": favorites
    }


# ─────────── OTHER ROUTES ─────────── #
@app.get("/user/analytics/{user_id}", response_model=schemas.UserAnalyticsResponse)
async def get_analytics(user_id: UUID, db: AsyncSession = Depends(get_async_session)):
    return await crud.get_user_analytics(db, user_id)


@app.put("/user/analytics/{user_id}", response_model=schemas.UserAnalyticsResponse)
async def update_analytics(
    user_id: UUID,
    update_data: schemas.UserAnalyticsUpdate,
    db: AsyncSession = Depends(get_async_session),
):
    return await crud.upsert_user_analytics(db, user_id, update_data)


# @app.post("/events/send", status_code=status.HTTP_202_ACCEPTED, tags=["Analytics"])
# async def track_play_event(
#     data: schemas.TrackPlayEventCreate,
# ):
#     event_data = data.dict()
#     await send_track_play_event(event_data)
#     return {"message": "Event sent to analytics."}
#
# @app.get("/analytics/user/{user_id}", response_model=schemas.UserAnalyticsResponse, tags=["Analytics"])
# async def get_user_profile(
#     user_id: UUID,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     analytics = await crud.get_user_analytics(session, user_id)
#     if not analytics:
#         raise HTTPException(404, detail="No analytics found for this user.")
#     return analytics
#
#
# @app.get("/analytics/user/{user_id}/events", response_model=list[schemas.TrackPlayEventResponse], tags=["Analytics"])
# async def get_user_events(
#     user_id: UUID,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     return await crud.get_user_play_events(session, user_id)
#

