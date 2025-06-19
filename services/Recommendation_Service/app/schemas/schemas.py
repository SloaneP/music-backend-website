from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class TrackResponse(BaseModel):
    id: str
    title: str
    artist: str
    track_url: str
    cover_url: str

class TrackShort(BaseModel):
    id: UUID
    title: Optional[str]
    artist: Optional[str]
    track_url: Optional[str] = None
    cover_url: Optional[str] = None

    class Config:
        from_attributes = True

class UserRecommendationBase(BaseModel):
    avg_duration_from_history: Optional[float]
    avg_release_year_from_history: Optional[float]
    top_genres_from_history: Optional[List[str]]
    top_moods_from_history: Optional[List[str]]

    avg_duration_from_favorites: Optional[float]
    avg_release_year_from_favorites: Optional[float]
    top_genres_from_favorites: Optional[List[str]]
    top_moods_from_favorites: Optional[List[str]]

    total_plays: Optional[int]
    total_favorites: Optional[int]
    most_favorite_tracks: Optional[List[UUID]]

    class Config:
        from_attributes = True

class UserRecommendationCreate(UserRecommendationBase):
    user_id: UUID

class UserRecommendationUpdate(UserRecommendationBase):
    recommended_tracks: Optional[List[UUID]]

class UserRecommendationResponse(UserRecommendationBase):
    id: UUID
    user_id: UUID
    recommended_tracks: Optional[List[UUID]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

class RecommendationBase(BaseModel):
    user_id: UUID
    recommended_track_ids: List[UUID]

class RecommendationCreate(RecommendationBase):
    pass

class RecommendationUpdate(BaseModel):
    recommended_track_ids: List[UUID]

class RecommendationOut(RecommendationBase):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True