from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime


class TrackPlayEventCreate(BaseModel):
    user_id: UUID4
    track_id: UUID4
    played_duration: float
    total_duration: float
    played_at: Optional[datetime] = None
    is_completed: str  # "yes" или "no"
    artist: Optional[str] = None
    genre: Optional[str] = None
    release_year: Optional[int] = None


class TrackPlayEventResponse(TrackPlayEventCreate):
    id: UUID4
    class Config:
        from_attributes = True


class UserAnalyticsCreate(BaseModel):
    user_id: UUID4
    avg_duration: Optional[float] = None
    avg_release_year: Optional[float] = None
    top_genres: Optional[str] = None
    top_artists: Optional[str] = None


class UserAnalyticsResponse(UserAnalyticsCreate):
    id: UUID4
    updated_at: datetime
    class Config:
        from_attributes = True
