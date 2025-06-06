import asyncio
import os
import random
import time
import urllib
import uuid

import redis.asyncio as redis
from tempfile import NamedTemporaryFile
from typing import List, Optional, Union
from uuid import UUID
import requests
from mutagen.mp3 import MP3

from fastapi import HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_, String
from sqlalchemy.orm import joinedload

from . import schemas
from .database import models

from .storage import extract_duration, delete_file, upload_files
from .storage import STORAGE_BASE_URL

# ─────────── TRACK ─────────── #
async def get_track(db: AsyncSession, track_id: UUID) -> models.Track | None:
    result = await db.execute(
        select(models.Track).where(models.Track.id == track_id)
    )
    return result.scalar_one_or_none()

async def get_tracks(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[schemas.TrackResponse]:
    result = await db.execute(
        select(models.Track).offset(skip).limit(limit)
    )
    tracks = result.scalars().all()

    for track in tracks:
        if not track.track_url.startswith("http"):
            track.track_url = STORAGE_BASE_URL + track.track_url
        if track.cover_url and not track.cover_url.startswith("http"):
            track.cover_url = STORAGE_BASE_URL + track.cover_url

    return tracks

# Redis (кэширование)
r = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

async def get_random_track(db: AsyncSession, user_id: UUID | None = None) -> schemas.TrackResponse | None:
    if user_id:
        user_tracks_key = f"user:{user_id}:tracks"
    else:
        user_tracks_key = "public:tracks"

    tracks = await r.smembers(user_tracks_key)

    if not tracks:
        result = await db.execute(select(models.Track))
        tracks = result.scalars().all()

        for track in tracks:
            track_id_str = str(track.id)
            if user_id:
                await r.sadd(user_tracks_key, track_id_str)
            else:
                await r.sadd("public:tracks", track_id_str)

        tracks = await r.smembers(user_tracks_key)

    random_track_id_str = random.choice(list(tracks))

    print(f"Random track ID for user {user_id} from Redis: {random_track_id_str}")

    try:
        random_track_id = uuid.UUID(random_track_id_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {e}")

    track = await get_track(db, random_track_id)

    if track:
        if user_id:
            await r.srem(user_tracks_key, random_track_id_str)
        return schemas.TrackResponse.from_orm(track)

    return None

# async def create_track_with_files(
#     db: AsyncSession,
#     track_data: schemas.TrackCreate,
#     files: list[UploadFile]
# ) -> models.Track:
#     if len(files) != 2:
#         raise HTTPException(status_code=400, detail="Exactly two files (audio and cover) must be provided.")
#
#     audio_file = next((f for f in files if f.filename.lower().endswith(".mp3")), None)
#     if not audio_file:
#         raise HTTPException(status_code=400, detail="MP3 file is required.")
#
#     duration = await extract_duration(audio_file)
#
#     uploaded_urls = await upload_files_async(files)
#
#     if "track_url" not in uploaded_urls or "cover_url" not in uploaded_urls:
#         raise HTTPException(status_code=400, detail="Both audio and cover files must be uploaded.")
#
#     new_track = models.Track(
#         title=track_data.title,
#         artist=track_data.artist,
#         duration=duration,
#         genre=track_data.genre,
#         mood=track_data.mood,
#         release_year=track_data.release_year,
#         track_url=uploaded_urls["track_url"],
#         cover_url=uploaded_urls["cover_url"]
#     )
#
#     db.add(new_track)
#     await db.commit()
#     await db.refresh(new_track)
#     return new_track


async def create_track_with_files(
    db: AsyncSession,
    track_data: schemas.TrackCreate,
    files: list[UploadFile]
) -> models.Track:
    if len(files) != 2:
        raise HTTPException(status_code=400, detail="Exactly two files (audio and cover) must be provided.")

    audio_file = next((f for f in files if f.filename.lower().endswith(".mp3")), None)
    if not audio_file:
        raise HTTPException(status_code=400, detail="MP3 file is required.")

    t1 = time.perf_counter()
    duration = await extract_duration(audio_file)
    t2 = time.perf_counter()
    print(f"Duration extraction took {t2 - t1:.2f} seconds")

    upload_results = await upload_files(files)
    t3 = time.perf_counter()
    print(f"File upload took {t3 - t2:.2f} seconds")

    uploaded_urls = upload_results

    if "track_url" not in uploaded_urls or "cover_url" not in uploaded_urls:
        raise HTTPException(status_code=400, detail="Both audio and cover files must be uploaded.")

    new_track = models.Track(
        title=track_data.title,
        artist=track_data.artist,
        duration=duration,
        genre=track_data.genre,
        mood=track_data.mood,
        release_year=track_data.release_year,
        track_url=uploaded_urls["track_url"],
        cover_url=uploaded_urls["cover_url"]
    )

    db.add(new_track)
    await db.commit()
    await db.refresh(new_track)
    return new_track

# async def create_track_with_files(
#     db: AsyncSession,
#     track_data: schemas.TrackCreate,
#     files: list
# ) -> models.Track:
#     # Ограничение на 2 файла (один аудио, одна обложка)
#     if len(files) != 2:
#         raise HTTPException(status_code=400, detail="Exactly two files (audio and cover) must be provided.")
#
#     uploaded_urls = await upload_files(files)
#
#     track_url = uploaded_urls.get("track_url")
#     cover_url = uploaded_urls.get("cover_url")
#
#     if not track_url or not cover_url:
#         raise HTTPException(status_code=400, detail="Both audio and cover files must be uploaded.")
#
#     audio_file_path = track_url.replace(STORAGE_BASE_URL, "")
#
#     try:
#         with NamedTemporaryFile(delete=False) as temp_audio_file:
#             temp_audio_file_path = temp_audio_file.name
#             response = requests.get(track_url)
#             if response.status_code == 200:
#                 temp_audio_file.write(response.content)
#             else:
#                 raise HTTPException(status_code=500, detail="Failed to download the audio file")
#
#         try:
#             audio = MP3(temp_audio_file_path)
#             duration = audio.info.length
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Failed to read duration from audio file: {e}")
#         finally:
#             os.remove(temp_audio_file_path)
#
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing audio file: {e}")
#
#     new_track = models.Track(
#         title=track_data.title,
#         artist=track_data.artist,
#         duration=duration,
#         genre=track_data.genre,
#         mood=track_data.mood,
#         release_year=track_data.release_year,
#         track_url=track_url,
#         cover_url=cover_url
#     )
#
#     db.add(new_track)
#     await db.commit()
#     await db.refresh(new_track)
#     return new_track

async def update_track(
        db: AsyncSession, track_id: UUID, track_in: schemas.TrackUpdate, email: str
) -> models.Track | None:
    result = await db.execute(
        select(models.Track).where(models.Track.id == track_id)
    )
    track = result.scalar_one_or_none()

    if track is None:
        return None

    # TODO: Добавить проверку владельца трека, когда появится связь с пользователями (изменить модель ТРЕКА!!!)
    # if track.publisher_email != email:
    #     raise HTTPException(status_code=403, detail="You do not have permission to update this track")

    for field, value in track_in.model_dump(exclude_unset=True).items():
        setattr(track, field, value)

    await db.commit()
    await db.refresh(track)
    return track

def extract_key(url: str) -> str:
        return urllib.parse.unquote(url.replace(STORAGE_BASE_URL, ""))

async def delete_track(db: AsyncSession, track_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        select(models.Track).where(models.Track.id == track_id)
    )
    track = result.scalar_one_or_none()

    if track is None:
        return False

    # TODO: Проверка владельца трека
    # if track.owner_id != user_id:
    #     raise HTTPException(status_code=403, detail="You do not have permission to delete this track")

    track_key = extract_key(track.track_url)
    cover_key = extract_key(track.cover_url)

    delete_file(track_key)
    delete_file(cover_key)

    await db.delete(track)
    await db.commit()
    return True

# async def delete_track(db: AsyncSession, track_id: UUID, user_id: UUID) -> bool:
#     result = await db.execute(
#         select(models.Track).where(models.Track.id == track_id)
#     )
#     track = result.scalar_one_or_none()
#
#     if track is None:
#         return False
#
#     # TODO: Добавить проверку на владельца трека (в будущем)
#     # if track.owner_id != user_id:
#     #     raise HTTPException(status_code=403, detail="You do not have permission to delete this track")
#
#     await db.delete(track)
#     await db.commit()
#     return True


# ─────────── SEARCH ─────────── #
async def search_tracks(
    db: AsyncSession,
    query: str,
    search_in: Optional[List[str]] = None,  # например: ["title"], ["artist"], ["title", "artist"], или None для всех
    skip: int = 0,
    limit: int = 20,
) -> list[schemas.TrackResponse]:
    if not query:
        return []

    if search_in is None or not search_in:
        # если параметр не передан, ищем по всем полям
        search_in = ["title", "artist", "genre", "mood"]

    conditions = []

    if "title" in search_in:
        conditions.append(models.Track.title.ilike(f"%{query}%"))
    if "artist" in search_in:
        conditions.append(models.Track.artist.ilike(f"%{query}%"))
    if "genre" in search_in:
        conditions.append(models.Track.genre.cast(String).ilike(f"%{query}%"))
    if "mood" in search_in:
        conditions.append(models.Track.mood.cast(String).ilike(f"%{query}%"))

    stmt = (
        select(models.Track)
        .where(or_(*conditions))
        .order_by(models.Track.title)
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(stmt)
    tracks = result.scalars().all()

    for track in tracks:
        if not track.track_url.startswith("http"):
            track.track_url = STORAGE_BASE_URL + track.track_url
        if track.cover_url and not track.cover_url.startswith("http"):
            track.cover_url = STORAGE_BASE_URL + track.cover_url

    return [schemas.TrackResponse.from_orm(track) for track in tracks]


# ─────────── PLAYLIST ─────────── #
async def create_playlist_with_cover(
    db: AsyncSession,
    name: str,
    is_public: bool,
    user_id: UUID,
    files: list[UploadFile]
) -> models.Playlist:
    if len(files) != 1:
        raise HTTPException(status_code=400, detail="Exactly one image file must be provided.")

    image_file = next((f for f in files if f.filename.lower().endswith((".jpg", ".jpeg", ".png"))), None)
    if not image_file:
        raise HTTPException(status_code=400, detail="Image file (.jpg/.jpeg/.png) is required.")

    upload_results = await upload_files(files)

    if "cover_url" not in upload_results:
        raise HTTPException(status_code=400, detail="Cover upload failed.")

    new_playlist = models.Playlist(
        name=name,
        is_public=is_public,
        cover_url=upload_results["cover_url"],
        user_id=user_id
    )

    db.add(new_playlist)
    await db.commit()
    await db.refresh(new_playlist)
    return new_playlist


async def get_user_playlists(db: AsyncSession, user_id: UUID) -> list[models.Playlist]:
    result = await db.execute(
        select(models.Playlist)
        .where(models.Playlist.user_id == user_id)
        .options(joinedload(models.Playlist.tracks))
    )
    return list(result.scalars().unique())

async def get_public_playlists(db: AsyncSession) -> list[models.Playlist]:
    result = await db.execute(
        select(models.Playlist)
        .where(models.Playlist.is_public == True)
        .options(joinedload(models.Playlist.tracks))
    )
    return result.unique().scalars().all()

async def get_playlist(db: AsyncSession, playlist_id: UUID, user_id: UUID) -> Optional[models.Playlist]:
    result = await db.execute(
        select(models.Playlist)
        .where(models.Playlist.id == playlist_id)
        .options(joinedload(models.Playlist.tracks))
    )
    playlist = result.unique().scalar_one_or_none()

    if playlist is None:
        return None

    if playlist.user_id != user_id and not playlist.is_public:
        return None

    return playlist

async def update_playlist(
    db: AsyncSession,
    playlist_id: UUID,
    user_id: UUID,
    data: schemas.PlaylistUpdate,
    user_role: str
) -> Optional[models.Playlist]:
    result = await db.execute(
        select(models.Playlist).where(models.Playlist.id == playlist_id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        return None

    if user_role != "Administrator" and playlist.user_id != user_id:
        return None

    update_data = data.dict(exclude_unset=True)
    if user_role != "Administrator":
        update_data.pop("is_public", None)

    for key, value in update_data.items():
        setattr(playlist, key, value)

    await db.commit()
    await db.refresh(playlist)
    return playlist

async def update_playlist_cover_with_file(
    db: AsyncSession,
    playlist_id: UUID,
    user_id: UUID,
    file: UploadFile,
    user_role: str
) -> models.Playlist:
    ext = file.filename.lower().split(".")[-1]
    if ext not in ["jpg", "jpeg", "png"]:
        raise HTTPException(status_code=400, detail="Only JPG or PNG files are allowed.")

    result = await db.execute(select(models.Playlist).where(models.Playlist.id == playlist_id))
    playlist = result.scalar_one_or_none()

    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    if user_role != "Administrator" and playlist.user_id != user_id:
        raise HTTPException(status_code=403, detail="You do not have permission to edit this playlist")

    upload_result = await upload_files([file])
    new_cover_url = upload_result.get("cover_url")

    if not new_cover_url:
        raise HTTPException(status_code=400, detail="Cover upload failed.")

    if playlist.cover_url:
        old_key = extract_key(playlist.cover_url)
        delete_file(old_key)

    playlist.cover_url = new_cover_url
    await db.commit()
    await db.refresh(playlist)
    return playlist

async def add_track_to_playlist(db: AsyncSession, playlist_id: UUID, track_id: UUID, user_id: UUID) -> schemas.PlaylistRead:
    playlist = await get_playlist(db, playlist_id, user_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found or you do not have access to it")

    track = await db.get(models.Track, track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if track not in playlist.tracks:
        playlist.tracks.append(track)
        await db.commit()
        await db.refresh(playlist)

    return jsonable_encoder(schemas.PlaylistRead.from_orm(playlist))

async def remove_track_from_playlist(db: AsyncSession, playlist_id: UUID, track_id: UUID, user_id: UUID) -> dict:
    playlist = await get_playlist(db, playlist_id, user_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found or you do not have access to it")

    if track_id not in [t.id for t in playlist.tracks]:
        raise HTTPException(status_code=404, detail="Track not found in this playlist")

    playlist.tracks = [t for t in playlist.tracks if t.id != track_id]
    await db.commit()
    return {"message": "Track removed from playlist"}

async def delete_playlist(db: AsyncSession, playlist_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        select(models.Playlist)
        .where(models.Playlist.id == playlist_id)
        .where(models.Playlist.user_id == user_id)
    )
    playlist = result.scalar_one_or_none()
    if not playlist:
        return False

    await db.delete(playlist)
    await db.commit()
    return True


# ─────────── FAVORITES ─────────── #
async def add_to_favorites(db: AsyncSession, user_id: UUID, track_id: UUID) -> models.FavoriteTrack:
    favorite = models.FavoriteTrack(user_id=user_id, track_id=track_id)
    db.add(favorite)
    try:
        await db.commit()
        await db.refresh(favorite)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Track already in favorites")
    return favorite

async def remove_from_favorites(db: AsyncSession, user_id: UUID, track_id: UUID) -> bool:
    result = await db.execute(
        delete(models.FavoriteTrack)
        .where(models.FavoriteTrack.user_id == user_id)
        .where(models.FavoriteTrack.track_id == track_id)
    )
    await db.commit()
    return result.rowcount > 0

async def get_user_favorites(db: AsyncSession, user_id: UUID) -> list[models.Track]:
    result = await db.execute(
        select(models.Track)
        .join(models.FavoriteTrack, models.FavoriteTrack.track_id == models.Track.id)
        .where(models.FavoriteTrack.user_id == user_id)
    )
    return result.scalars().all()


# ─────────── PLAY HISTORY ─────────── #
async def add_play_history(
    db: AsyncSession, user_id: UUID, track_id: UUID
) -> models.PlayHistory:
    track_exists = await db.execute(
        select(models.Track.id).where(models.Track.id == track_id)
    )
    if not track_exists.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Track not found")

    count_result = await db.execute(
        select(func.count(models.PlayHistory.id)).where(models.PlayHistory.user_id == user_id)
    )
    history_count = count_result.scalar_one() or 0
    if history_count >= 20:
        oldest_result = await db.execute(
            select(models.PlayHistory)
            .where(models.PlayHistory.user_id == user_id)
            .order_by(models.PlayHistory.timestamp.asc())
            .limit(1)
        )
        oldest_entry = oldest_result.scalar_one_or_none()
        if oldest_entry:
            await db.delete(oldest_entry)

    new_entry = models.PlayHistory(user_id=user_id, track_id=track_id)
    db.add(new_entry)
    await db.commit()
    await db.refresh(new_entry)
    return new_entry

async def update_play_history(
    db: AsyncSession, user_id: UUID, entry_id: UUID, played_duration: float
) -> models.PlayHistory:
    result = await db.execute(
        select(models.PlayHistory)
        .where(models.PlayHistory.id == entry_id)
        .where(models.PlayHistory.user_id == user_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="History entry not found")

    entry.played_duration = played_duration
    await db.commit()
    await db.refresh(entry)
    return entry

async def get_recent_play_history(
    db: AsyncSession,
    user_id: UUID,
    limit: int = 20,
    offset: int = 0
) -> list[schemas.PlayHistoryResponse]:
    result = await db.execute(
        select(models.PlayHistory)
        .where(models.PlayHistory.user_id == user_id)
        .order_by(models.PlayHistory.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .options(joinedload(models.PlayHistory.track))
    )
    return result.scalars().all()

# ─────────── ALBUM ─────────── #

# async def create_album(
#     db: AsyncSession,
#     album_data: schemas.AlbumCreate,
#     cover_file: Optional[UploadFile]
# ):
#     album = models.Album(
#         title=album_data.title,
#         artist=album_data.artist,
#         release_year=album_data.release_year
#     )
#
#     if cover_file:
#         uploaded = await upload_files([cover_file])
#         album.cover_url = uploaded.get("cover_url")
#
#     if album_data.track_ids:
#         result = await db.execute(select(models.Track).where(models.Track.id.in_(album_data.track_ids)))
#         album.tracks = result.scalars().all()
#
#     db.add(album)
#     await db.commit()
#     await db.refresh(album)
#
#     return album
#
#
# async def get_album(db: AsyncSession, album_id: UUID) -> models.Album | None:
#     result = await db.execute(
#         select(models.Album).options(joinedload(models.Album.tracks)).where(models.Album.id == album_id))
#     return result.unique().scalar_one_or_none()
#
# async def get_albums(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Album]:
#     result = await db.execute(select(models.Album).offset(skip).limit(limit))
#     return result.scalars().all()
#
#
# async def update_album(db: AsyncSession, album_id: UUID, album_in: schemas.AlbumUpdate) -> models.Album | None:
#     result = await db.execute(select(models.Album).where(models.Album.id == album_id))
#     album = result.scalar_one_or_none()
#     if not album:
#         return None
#
#     for field, value in album_in.dict(exclude_unset=True).items():
#         setattr(album, field, value)
#
#     await db.commit()
#     await db.refresh(album)
#     return album
#
#
#
# async def delete_album(db: AsyncSession, album_id: UUID) -> bool:
#     result = await db.execute(select(models.Album).where(models.Album.id == album_id))
#     album = result.scalar_one_or_none()
#     if not album:
#         return False
#
#     for track in album.tracks:
#         track.albums.remove(album)
#
#     await db.delete(album)
#     await db.commit()
#     return True
#
#
#
# async def upload_album_cover(file: UploadFile) -> str:
#     """Загружает обложку альбома через общую функцию upload_files и возвращает URL."""
#
#     uploaded = await upload_files([file])
#
#     cover_url = uploaded.get("cover_url")
#     if not cover_url:
#         raise HTTPException(status_code=400, detail="Cover file must be an image (jpg/jpeg/png)")
#
#     return cover_url