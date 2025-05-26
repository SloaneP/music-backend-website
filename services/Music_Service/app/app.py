import json
import logging
from typing import List, Optional
from uuid import UUID

import jwt
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, Form, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from . import config, schemas, crud
from .broker.rabbitmq_producer import send_track_play_event
from .database import get_async_session, db_initializer
from . import storage

from .database.enums import GenreEnum, MoodEnum


cfg = config.load_config()
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
    except Exception as e:
        logger.exception("Failed to initialize database: %s", e)


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
    logger.info(f"Authorization header: {auth_header}")

    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("Authorization header missing or invalid")
        return None

    token = auth_header.split(" ")[1]
    logger.info(f"Extracted token: {token}")

    user_data = extract_email_data(token)
    logger.info(f"Extracted user data: {user_data}")

    if not user_data:
        logger.warning("Invalid or expired token")
        return None

    email, user_id = user_data
    logger.info(f"Authenticated user: {email} (ID: {user_id})")
    return email, user_id

# async def get_current_user(request: Request) -> tuple[str, UUID]:
#     auth_header = request.headers.get("authorization")
#     logger.info(f"Authorization header: {auth_header}")
#
#     if not auth_header or not auth_header.startswith("Bearer "):
#         logger.warning("Authorization header missing or invalid")
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Authorization header missing or invalid",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#
#     token = auth_header.split(" ")[1]
#     logger.info(f"Extracted token: {token}")
#
#     user_data = extract_email_data(token)
#     logger.info(f"Extracted user data: {user_data}")
#
#     if not user_data:
#         logger.warning("Invalid or expired token")
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid or expired token",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#
#     email, user_id = user_data
#     logger.info(f"Authenticated user: {email} (ID: {user_id})")
#     return email, user_id

@app.post("/tracks/play", tags=["Tracks"])
async def track_play(event: dict):
    await send_track_play_event(event)
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/docs")


# Получить список треков
@app.get("/tracks", response_model=list[schemas.TrackResponse], tags=["Tracks"])
async def get_tracks(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_async_session)
):
    return await crud.get_tracks(session, skip, limit)


# Получить трек по ID
@app.get("/tracks/{track_id}", response_model=schemas.TrackResponse, tags=["Tracks"])
async def get_track(
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session)
):
    track = await crud.get_track(session, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track

# # Получить случайный трек
# @app.get("/track/random-track", response_model=schemas.TrackResponse, tags=["Tracks"])
# async def random_track(db: AsyncSession = Depends(get_async_session)):
#     track = await crud.get_random_track(db)
#     if not track:
#         raise HTTPException(status_code=404, detail="Track not found")
#     return track

# @app.get("/track/random-track", response_model=schemas.TrackResponse, tags=["Tracks"])
# async def random_track(db: AsyncSession = Depends(get_async_session), user_data: tuple[str, UUID] = Depends(get_current_user)):
#     email, user_id = user_data
#     track = await crud.get_random_track(db, user_id)
#     if not track:
#         raise HTTPException(status_code=404, detail="Track not found")
#     return track

@app.get("/track/random-track", response_model=schemas.TrackResponse, tags=["Tracks"])
async def random_track(
    db: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    if user_data:  # Если пользователь авторизован
        email, user_id = user_data
        track = await crud.get_random_track(db, user_id)
    else:  # Если пользователь не авторизован
        track = await crud.get_random_track(db)

    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return track

###

@app.post("/tracks/upload", response_model=schemas.TrackResponse, tags=["Tracks"])
async def create_track_with_files(
    title: str = Form(...),
    artist: str = Form(...),
    genre: GenreEnum = Form(...),
    mood: Optional[MoodEnum] = Form(...),
    release_year: int = Form(None),
    files: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    track_data = schemas.TrackCreate(
        title=title,
        artist=artist,
        genre=genre,
        mood=mood,
        release_year=release_year,
        track_url="http://temp",  # временно, заменится в CRUD
        cover_url="http://temp"   # временно, заменится в CRUD
    )
    return await crud.create_track_with_files(session, track_data, files)



# Обновить трек
@app.put("/tracks/{track_id}", response_model=schemas.TrackResponse, tags=["Tracks"])
async def update_track(
    track_id: UUID,
    title: Optional[str] = Form(None),
    artist: Optional[str] = Form(None),
    genre: Optional[GenreEnum] = Form(None),
    mood: Optional[MoodEnum] = Form(None),
    release_year: Optional[int] = Form(None),
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user),
):
    update_data = {k: v for k, v in {
        "title": title,
        "artist": artist,
        "genre": genre,
        "mood": mood,
        "release_year": release_year,
    }.items() if v is not None}

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    track_update = schemas.TrackUpdate(**update_data)
    email, _ = user_data
    updated_track = await crud.update_track(session, track_id, track_update, email)
    if not updated_track:
        raise HTTPException(status_code=404, detail="Track not found")
    return updated_track


# Удалить трек
@app.delete("/tracks/{track_id}", tags=["Tracks"])
async def delete_track(
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    result = await crud.delete_track(session, track_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Track not found")
    return {"message": "Track deleted successfully"}


# ─────────── STORAGE ROUTES ─────────── #

@app.get("/files", tags=["Cloud Storage"])
async def list_cloud_files():
    return storage.list_files()

@app.get("/files/url", tags=["Cloud Storage"])
async def generate_file_url(file_path: str):
    return {"url": storage.generate_presigned_url(file_path)}

@app.post("/files/upload", tags=["Cloud Storage"])
async def upload_to_cloud(files: List[UploadFile] = File(...)):
    return await storage.upload_files(files)

@app.get("/files/delete", tags=["Cloud Storage"])
async def delete_from_cloud(file_path: str):
    return storage.delete_file(file_path)

# ─────────── PLAYLISTS ROUTES ─────────── #

# Создать плейлист
@app.post("/playlists", response_model=schemas.PlaylistRead, tags=["Playlists"])
async def create_playlist(
    data: schemas.PlaylistCreate,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    email, user_id = user_data
    return await crud.create_playlist(session, data, user_id)

# Получить плейлисты текущего пользователя
@app.get("/playlists", response_model=list[schemas.PlaylistRead], tags=["Playlists"])
async def list_playlists(
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    return await crud.get_user_playlists(session, user_id)

# Получить конкретный плейлист
@app.get("/playlists/{playlist_id}", response_model=schemas.PlaylistRead, tags=["Playlists"])
async def get_playlist(
    playlist_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    playlist = await crud.get_playlist(session, playlist_id, user_id)
    if not playlist:
        raise HTTPException(404, detail="Playlist not found or access denied")
    return playlist

# Добавить трек в плейлист
@app.post("/playlists/{playlist_id}/tracks/{track_id}", tags=["Playlists"])
async def add_track(
    playlist_id: UUID,
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    return await crud.add_track_to_playlist(session, playlist_id, track_id, user_id)

# Удалить трек из плейлиста
@app.delete("/playlists/{playlist_id}/tracks/{track_id}", tags=["Playlists"])
async def remove_track(
    playlist_id: UUID,
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    return await crud.remove_track_from_playlist(session, playlist_id, track_id, user_id)

# Удалить плейлист
@app.delete("/playlists/{playlist_id}", tags=["Playlists"])
async def delete_playlist(
    playlist_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    email, user_id = user_data
    success = await crud.delete_playlist(session, playlist_id, user_id)
    if not success:
        raise HTTPException(404, detail="Playlist not found")
    return {"message": "Playlist deleted"}


# ───── Favorites ───── #

@app.post("/favorites/{track_id}", tags=["Favorites"])
async def add_to_favorites(
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    return await crud.add_to_favorites(session, user_id, track_id)


@app.delete("/favorites/{track_id}", tags=["Favorites"])
async def remove_from_favorites(
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    if not await crud.remove_from_favorites(session, user_id, track_id):
        raise HTTPException(404, detail="Favorite not found")
    return {"message": "Removed from favorites"}


@app.get("/favorites", response_model=List[schemas.TrackResponse], tags=["Favorites"])
async def get_favorites(
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    return await crud.get_user_favorites(session, user_id)


# ───── Play History ───── #

@app.post("/history/{track_id}", response_model=schemas.PlayHistoryResponse, tags=["History"])
async def add_play_history(
    track_id: UUID,
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    history_entry = await crud.add_play_history(session, user_id, track_id)
    return history_entry


@app.get("/history", response_model=List[schemas.PlayHistoryResponse], tags=["History"])
async def get_history(
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
    user_data: tuple[str, UUID] = Depends(get_current_user)
):
    _, user_id = user_data
    history = await crud.get_recent_play_history(session, user_id, limit)
    return history


# ─────────── ALBUMS ROUTES ─────────── #

# Создать альбом
# @app.post("/albums", response_model=schemas.AlbumResponse, tags=["Albums"])
# async def create_album(
#     title: str = Form(...),
#     artist: str = Form(...),
#     release_year: Optional[int] = Form(None),
#     track_ids: Optional[str] = Form(None),
#     cover_file: Optional[UploadFile] = File(None),
#     db: AsyncSession = Depends(get_async_session)
# ):
#     parsed_track_ids = json.loads(track_ids) if track_ids else []
#
#     album_data = schemas.AlbumCreate(
#         title=title,
#         artist=artist,
#         release_year=release_year,
#         track_ids=parsed_track_ids
#     )
#
#     return await crud.create_album(db, album_data, cover_file)
#
#
# # Получить список альбомов
# @app.get("/albums", response_model=list[schemas.AlbumResponse], tags=["Albums"])
# async def get_albums(
#     skip: int = 0,
#     limit: int = 100,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     return await crud.get_albums(session, skip, limit)
#
#
# # Получить альбом по ID
# @app.get("/albums/{album_id}", response_model=schemas.AlbumResponse, tags=["Albums"])
# async def get_album(
#     album_id: UUID,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     album = await crud.get_album(session, album_id)
#     if album is None:
#         raise HTTPException(status_code=404, detail="Album not found")
#     return album
#
#
# # Обновить альбом
# @app.put("/albums/{album_id}", response_model=schemas.AlbumResponse, tags=["Albums"])
# async def update_album(
#     album_id: UUID,
#     album_in: schemas.AlbumUpdate,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     album = await crud.update_album(session, album_id, album_in)
#     if album is None:
#         raise HTTPException(status_code=404, detail="Album not found")
#     return album
#
#
# # Удалить альбом
# @app.delete("/albums/{album_id}", tags=["Albums"])
# async def delete_album(
#     album_id: UUID,
#     session: AsyncSession = Depends(get_async_session)
# ):
#     success = await crud.delete_album(session, album_id)
#     if not success:
#         raise HTTPException(status_code=404, detail="Album not found")
#     return {"message": "Album deleted successfully"}