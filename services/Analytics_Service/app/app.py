import asyncio
import logging
from uuid import UUID
from typing import Optional

import jwt
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


consume_task = None

@app.on_event("startup")
async def startup():
    global consume_task
    try:
        await db_initializer.init_db(str(cfg.PG_ASYNC_DSN))
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.exception("Failed to initialize database: %s", e)

    consume_task = asyncio.create_task(consume_track_play_events())

@app.on_event("shutdown")
async def shutdown():
    global consume_task
    if consume_task:
        consume_task.cancel()
        try:
            await consume_task
        except asyncio.CancelledError:
            logger.info("consume_track_play_events task cancelled successfully")


def extract_user_id(token: str) -> Optional[UUID]:
    try:
        payload = jwt.decode(
            token,
            cfg.JWT_SECRET,
            algorithms=["HS256"],
            audience=["fastapi-users:auth"]
        )
        user_id = payload.get("sub")
        return UUID(user_id)
    except Exception as e:
        logger.warning(f"JWT decode error: {e}")
        return None


async def get_current_user_id(request: Request) -> Optional[UUID]:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    token = auth_header.split(" ")[1]
    return extract_user_id(token)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

# @app.post("/events/send", response_model=schemas.TrackPlayEventResponse, tags=["Analytics"])
# async def track_play_event(
#     data: schemas.TrackPlayEventCreate,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     event_data = data.dict()
#     await send_track_play_event(event_data)
#     return data

@app.post("/events/send", status_code=status.HTTP_202_ACCEPTED, tags=["Analytics"])
async def track_play_event(
    data: schemas.TrackPlayEventCreate,
):
    event_data = data.dict()
    await send_track_play_event(event_data)
    return {"message": "Event sent to analytics."}

@app.get("/analytics/user/{user_id}", response_model=schemas.UserAnalyticsResponse, tags=["Analytics"])
async def get_user_profile(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session)
):
    analytics = await crud.get_user_analytics(session, user_id)
    if not analytics:
        raise HTTPException(404, detail="No analytics found for this user.")
    return analytics


@app.get("/analytics/user/{user_id}/events", response_model=list[schemas.TrackPlayEventResponse], tags=["Analytics"])
async def get_user_events(
    user_id: UUID,
    session: AsyncSession = Depends(get_async_session)
):
    return await crud.get_user_play_events(session, user_id)


