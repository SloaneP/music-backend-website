import logging
from uuid import UUID
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
import jwt
from .crud import get_recommended_tracks, get_recommended_tracks_from_db
from .database import get_async_session, db_initializer
from .config import load_config
from .fetch_from_music_service.fetch_all_tracks import fetch_all_tracks_from_music_service
from .schemas import schemas
from fastapi_utils.tasks import repeat_every

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

app = FastAPI(
    title=cfg.SERVICE_NAME,
    version="1.0.0",
    redirect_slashes=False
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
    await db_initializer.init_db(str(cfg.PG_ASYNC_DSN))
    logger.info("DB initialized.")


@app.on_event("startup")
@repeat_every(seconds=300, wait_first=True)
async def refresh_music_cache_task() -> None:
    logger.info("Background task: обновляем кэш треков в Redis")
    try:
        await fetch_all_tracks_from_music_service()
        logger.info("Кэш треков успешно обновлен")
    except Exception as e:
        logger.error(f"Ошибка при обновлении кэша треков: {e}")

def extract_email_data(token: str) -> Optional[tuple[str, UUID]]:
    try:
        data = jwt.decode(token, cfg.JWT_SECRET, algorithms=["HS256"], audience=["fastapi-users:auth"])
        email = data.get("email")
        user_id = data.get("sub")
        if email and user_id:
            return email, UUID(user_id)
    except Exception as e:
        logger.warning(f"JWT decode failed: {e}")
        return None
    return None


async def get_current_user(request: Request) -> tuple[str, UUID]:
    auth_header = request.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth")
    token = auth_header.split(" ")[1]
    user_data = extract_email_data(token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_data


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")

@app.get("/recommendations/{user_id}", response_model=list[schemas.TrackResponse])
async def get_user_recommendations(user_id: UUID, db: AsyncSession = Depends(get_async_session)):
    """
    Получить рекомендации для пользователя по user_id.
    """
    return await get_recommended_tracks_from_db(db, user_id)

@app.get("/my-wave", response_model=list[schemas.TrackResponse])
async def my_wave(
    user: tuple[str, UUID] = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    email, user_id = user
    return await get_recommended_tracks(db, user_id)