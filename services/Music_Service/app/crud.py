import os

from tempfile import NamedTemporaryFile
from typing import List, Optional
from uuid import UUID
import requests
from mutagen.mp3 import MP3

from fastapi import HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from sqlalchemy.orm import joinedload

from . import schemas
from .database import models

from .storage import upload_files
from .storage import STORAGE_BASE_URL

# Получение трека по ID
async def get_track(db: AsyncSession, track_id: UUID) -> models.Track | None:
    result = await db.execute(
        select(models.Track).where(models.Track.id == track_id)
    )
    return result.scalar_one_or_none()


# Получение списка треков с пагинацией
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

async def create_track_with_files(
    db: AsyncSession,
    track_data: schemas.TrackCreate,
    files: list
) -> models.Track:
    # Ограничение на 2 файла (один аудио, одна обложка)
    if len(files) != 2:
        raise HTTPException(status_code=400, detail="Exactly two files (audio and cover) must be provided.")

    uploaded_urls = await upload_files(files)

    track_url = uploaded_urls.get("track_url")
    cover_url = uploaded_urls.get("cover_url")

    if not track_url or not cover_url:
        raise HTTPException(status_code=400, detail="Both audio and cover files must be uploaded.")

    audio_file_path = track_url.replace(STORAGE_BASE_URL, "")

    try:
        with NamedTemporaryFile(delete=False) as temp_audio_file:
            temp_audio_file_path = temp_audio_file.name
            response = requests.get(track_url)
            if response.status_code == 200:
                temp_audio_file.write(response.content)
            else:
                raise HTTPException(status_code=500, detail="Failed to download the audio file")

        try:
            audio = MP3(temp_audio_file_path)
            duration = audio.info.length
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read duration from audio file: {e}")
        finally:
            os.remove(temp_audio_file_path)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing audio file: {e}")

    new_track = models.Track(
        title=track_data.title,
        artist=track_data.artist,
        duration=duration,
        genre=track_data.genre,
        release_year=track_data.release_year,
        track_url=track_url,
        cover_url=cover_url
    )

    db.add(new_track)
    await db.commit()
    await db.refresh(new_track)
    return new_track


# Обновление существующего трека
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


# Удаление трека
async def delete_track(db: AsyncSession, track_id: UUID, user_id: UUID) -> bool:
    # Получаем трек
    result = await db.execute(
        select(models.Track).where(models.Track.id == track_id)
    )
    track = result.scalar_one_or_none()

    if track is None:
        return False

    # TODO: Добавить проверку на владельца трека (в будущем)
    # if track.owner_id != user_id:
    #     raise HTTPException(status_code=403, detail="You do not have permission to delete this track")

    await db.delete(track)
    await db.commit()
    return True

### Playlist
async def create_playlist(db: AsyncSession, playlist_data: schemas.PlaylistCreate, user_id: UUID) -> models.Playlist:
    playlist = models.Playlist(
        name=playlist_data.name,
        user_id=user_id
    )
    db.add(playlist)
    await db.commit()
    await db.refresh(playlist)
    return playlist

async def get_playlists(db: AsyncSession) -> list[models.Playlist]:
    result = await db.execute(
        select(models.Playlist).options(joinedload(models.Playlist.tracks))
    )
    return result.unique().scalars().all()

async def get_user_playlists(db: AsyncSession, user_id: UUID) -> list[models.Playlist]:
    result = await db.execute(
        select(models.Playlist)
        .where(models.Playlist.user_id == user_id)
        .options(joinedload(models.Playlist.tracks))
    )
    return list(result.scalars().unique())

async def get_playlist(db: AsyncSession, playlist_id: UUID, user_id: UUID) -> Optional[models.Playlist]:
    result = await db.execute(
        select(models.Playlist)
        .where(models.Playlist.id == playlist_id)
        .where(models.Playlist.user_id == user_id)
    )
    return result.scalar_one_or_none()

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

async def add_play_history(db: AsyncSession, user_id: UUID, track_id: UUID) -> schemas.PlayHistoryResponse:
    # Проверяем, не превышен ли лимит (100 записей)
    history_count = await db.execute(
        select(func.count(models.PlayHistory.id))
        .where(models.PlayHistory.user_id == user_id)
    )
    if history_count.scalar() >= 100:
        # Удаляем самый старый трек
        oldest_entry = await db.execute(
            select(models.PlayHistory)
            .where(models.PlayHistory.user_id == user_id)
            .order_by(models.PlayHistory.timestamp.asc())
            .limit(1)
        )
        oldest_entry = oldest_entry.scalar_one_or_none()
        if oldest_entry:
            await db.delete(oldest_entry)

    # Добавляем новый трек
    history = models.PlayHistory(user_id=user_id, track_id=track_id)
    db.add(history)
    await db.commit()
    await db.refresh(history)
    return history


async def get_recent_play_history(db: AsyncSession, user_id: UUID, limit: int = 10) -> list[schemas.PlayHistoryResponse]:
    result = await db.execute(
        select(models.PlayHistory)
        .where(models.PlayHistory.user_id == user_id)
        .order_by(models.PlayHistory.timestamp.desc())
        .limit(limit)
        .options(joinedload(models.PlayHistory.track))
    )
    return result.scalars().all()

### Album

# Создание альбома
async def create_album(
    db: AsyncSession,
    album_data: schemas.AlbumCreate,
    cover_file: Optional[UploadFile]
):
    album = models.Album(
        title=album_data.title,
        artist=album_data.artist,
        release_year=album_data.release_year
    )

    # Обработка обложки
    if cover_file:
        uploaded = await upload_files([cover_file])
        album.cover_url = uploaded.get("cover_url")

    # Добавление треков (если переданы)
    if album_data.track_ids:
        result = await db.execute(select(models.Track).where(models.Track.id.in_(album_data.track_ids)))
        album.tracks = result.scalars().all()

    db.add(album)
    await db.commit()
    await db.refresh(album)

    return album


# Получение одного альбома
async def get_album(db: AsyncSession, album_id: UUID) -> models.Album | None:
    result = await db.execute(
        select(models.Album).options(joinedload(models.Album.tracks)).where(models.Album.id == album_id))
    return result.unique().scalar_one_or_none()

# Получение всех альбомов
async def get_albums(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[models.Album]:
    result = await db.execute(select(models.Album).offset(skip).limit(limit))
    return result.scalars().all()


# Обновление альбома
async def update_album(db: AsyncSession, album_id: UUID, album_in: schemas.AlbumUpdate) -> models.Album | None:
    result = await db.execute(select(models.Album).where(models.Album.id == album_id))
    album = result.scalar_one_or_none()
    if not album:
        return None

    for field, value in album_in.dict(exclude_unset=True).items():
        setattr(album, field, value)

    await db.commit()
    await db.refresh(album)
    return album


# Удаление альбома
async def delete_album(db: AsyncSession, album_id: UUID) -> bool:
    result = await db.execute(select(models.Album).where(models.Album.id == album_id))
    album = result.scalar_one_or_none()
    if not album:
        return False

    # Обнуляем связи с альбомом у треков
    for track in album.tracks:
        track.albums.remove(album)

    await db.delete(album)
    await db.commit()
    return True



async def upload_album_cover(file: UploadFile) -> str:
    """Загружает обложку альбома через общую функцию upload_files и возвращает URL."""

    uploaded = await upload_files([file])

    cover_url = uploaded.get("cover_url")
    if not cover_url:
        raise HTTPException(status_code=400, detail="Cover file must be an image (jpg/jpeg/png)")

    return cover_url