import uuid
from sqlalchemy import Column, DateTime, Float, Integer, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from .database import Base, SCHEMA

class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True, unique=True)
    recommended_track_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class UserRecommendation(Base):
    __tablename__ = "user_recommendations"
    __table_args__ = {"schema": SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), unique=True, nullable=False)

    avg_duration_from_history = Column(Float, nullable=True)
    avg_release_year_from_history = Column(Float, nullable=True)
    top_genres_from_history = Column(JSONB, nullable=True)
    top_moods_from_history = Column(JSONB, nullable=True)

    avg_duration_from_favorites = Column(Float, nullable=True)
    avg_release_year_from_favorites = Column(Float, nullable=True)
    top_genres_from_favorites = Column(JSONB, nullable=True)
    top_moods_from_favorites = Column(JSONB, nullable=True)

    total_plays = Column(Integer, nullable=True)
    total_favorites = Column(Integer, nullable=True)
    most_favorite_tracks = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    recommended_tracks = Column(ARRAY(UUID(as_uuid=True)), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
