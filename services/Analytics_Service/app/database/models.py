from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from .database import Base, SCHEMA


class UserAnalytics(Base):
    __tablename__ = "user_analytics"
    __table_args__ = {'schema': SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, unique=True)

    avg_duration = Column(Float, nullable=True)
    avg_release_year = Column(Float, nullable=True)
    top_genres = Column(String, nullable=True)
    top_artists = Column(String, nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrackPlayEvent(Base):
    __tablename__ = "track_play_events"
    __table_args__ = {'schema': SCHEMA}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    track_id = Column(UUID(as_uuid=True), nullable=False)
    played_duration = Column(Float, nullable=False)
    total_duration = Column(Float, nullable=False)
    played_at = Column(DateTime(timezone=True), server_default=func.now())
    is_completed = Column(String, nullable=False)  # "yes" / "no"
    artist = Column(String, nullable=True)
    genre = Column(String, nullable=True)
    release_year = Column(Integer, nullable=True)
