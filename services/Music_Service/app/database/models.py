from sqlalchemy.dialects.postgresql import UUID
import uuid

from sqlalchemy import Column, String, Integer, Float, Table, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import relationship

from .database import Base, SCHEMA

from sqlalchemy import Enum as PgEnum
from .enums import MoodEnum, GenreEnum

# Таблица для связи треков и альбомов
album_track_association = Table(
    'album_track_association', Base.metadata,
    Column('album_id', UUID(as_uuid=True), ForeignKey('music.albums.id', ondelete="CASCADE"), primary_key=True),
    Column('track_id', UUID(as_uuid=True), ForeignKey('music.tracks.id', ondelete="CASCADE"), primary_key=True),
    schema="music"
)
# Таблица для связи плейлистов и треков
playlist_track = Table(
    "playlist_track",
    Base.metadata,
    Column("playlist_id", UUID(as_uuid=True), ForeignKey("music.playlists.id", ondelete="CASCADE"), primary_key=True),
    Column("track_id", UUID(as_uuid=True), ForeignKey("music.tracks.id", ondelete="CASCADE"), primary_key=True),
    schema="music"
)


class Track(Base):
    __tablename__ = "tracks"
    __table_args__ = {'schema': 'music'}

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    duration = Column(Float, nullable=False)
    # genre = Column(String, nullable=False)
    genre = Column(PgEnum(GenreEnum, name="genre_enum", create_type=True), nullable=False)
    mood = Column(PgEnum(MoodEnum, name="mood_enum", create_type=True), nullable=True)
    release_year = Column(Integer)
    track_url = Column(String, nullable=False)
    cover_url = Column(String, nullable=True)

    albums = relationship(
        "Album",
        secondary=album_track_association,
        back_populates="tracks",
        lazy="selectin"
    )
    playlists = relationship(
        "Playlist",
        secondary=playlist_track,
        back_populates="tracks",
        lazy="selectin"
    )

class Playlist(Base):
    __tablename__ = "playlists"
    __table_args__ = {'schema': 'music'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)


    tracks = relationship(
        "Track",
        secondary=playlist_track,
        back_populates="playlists",
        lazy = "selectin"
    )


class PlayHistory(Base):
    __tablename__ = "play_history"
    __table_args__ = {'schema': 'music'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    track_id = Column(UUID(as_uuid=True), ForeignKey("music.tracks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    played_duration = Column(Float, nullable=True)

    track = relationship("Track", lazy="selectin")

class FavoriteTrack(Base):
    __tablename__ = "favorite_tracks"
    __table_args__ = (
        UniqueConstraint("user_id", "track_id", name="uq_user_track_like"),
        {'schema': 'music'}
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    track_id = Column(UUID(as_uuid=True), ForeignKey("music.tracks.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    track = relationship("Track", lazy="selectin")

class Album(Base):
    __tablename__ = "albums"
    __table_args__ = {'schema': 'music'}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=False)
    release_year = Column(Integer)
    cover_url = Column(String)

    tracks = relationship(
        "Track",
        secondary=album_track_association,
        back_populates="albums",
        lazy="selectin"
    )