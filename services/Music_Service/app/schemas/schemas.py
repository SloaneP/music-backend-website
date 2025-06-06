from datetime import datetime
from uuid import UUID

from fastapi import UploadFile
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List
from ..database.enums import MoodEnum, GenreEnum

class TrackBase(BaseModel):
    title: str
    artist: str
    duration: float
    genre: GenreEnum
    mood: Optional[MoodEnum] = None
    release_year: Optional[int] = None
    track_url: HttpUrl
    cover_url: Optional[HttpUrl] = None


class TrackCreate(BaseModel):
    title: str
    artist: str
    genre: GenreEnum
    mood: Optional[MoodEnum] = None
    release_year: Optional[int] = None


class TrackUpdate(BaseModel):
    """
    Схема для обновления трека (все поля необязательные)
    """
    title: Optional[str] = None
    artist: Optional[str] = None
    genre: Optional[GenreEnum] = None
    mood: Optional[MoodEnum] = None
    release_year: Optional[int] = None


class TrackResponse(TrackBase):
    """
    Схема для возврата данных пользователю
    """
    id: UUID

    class Config:
        from_attributes = True

# Playlist schemas
class PlaylistBase(BaseModel):
    name: str

class PlaylistCreate(PlaylistBase):
    is_public: Optional[bool] = False
    cover_url: Optional[str] = None

class PlaylistRead(PlaylistBase):
    id: UUID
    cover_url: Optional[str] = None
    tracks: List[TrackResponse] = []

    class Config:
        from_attributes = True

class PlaylistUpdate(BaseModel):
    name: Optional[str] = None
    is_public: Optional[bool] = None
    cover_url: Optional[str] = None

class FavoriteTrackCreate(BaseModel):
    user_id: UUID
    track_id: UUID

class FavoriteTrackResponse(BaseModel):
    id: UUID
    user_id: UUID
    track_id: UUID
    timestamp: datetime
    track: TrackResponse

    class Config:
        from_attributes = True

class PlayHistoryCreate(BaseModel):
    user_id: UUID
    track_id: UUID


class PlayHistoryUpdate(BaseModel):
    played_duration: float = Field(..., ge=0)


class PlayHistoryResponse(BaseModel):
    id: UUID
    user_id: UUID
    track_id: UUID
    timestamp: datetime
    played_duration: Optional[float]
    track: Optional["TrackResponse"]

    class Config:
        from_attributes = True

### Album

class AlbumBase(BaseModel):
    title: str
    artist: str
    release_year: Optional[int] = None
    track_ids: Optional[List[UUID]] = []

class AlbumCreate(BaseModel):
    title: str
    artist: str
    release_year: Optional[int] = None
    cover_image: Optional[UploadFile] = None

class AlbumUpdate(BaseModel):
    title: Optional[str] = None
    artist: Optional[str] = None
    release_year: Optional[int] = None
    cover_url: Optional[HttpUrl] = None

class AlbumResponse(AlbumBase):
    id: UUID
    title: str
    artist: str
    release_year: Optional[int]
    cover_url: Optional[HttpUrl]
    tracks: List[TrackResponse] = []

    class Config:
        from_attributes = True