from fastapi import Depends
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import mapped_column, relationship
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase

from .database import Base, SCHEMA, get_async_session
class Group(Base):
    __tablename__ = "group"
    __table_args__ = {'schema': SCHEMA}

    id = Column(Integer, primary_key=True, default=0, index=True)
    name = Column(String)


class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "user"
    __table_args__ = {'schema':  SCHEMA}

    username = Column(String(length=128), nullable=True)
    group_id = mapped_column(ForeignKey(f"{SCHEMA}.group.id"))
    group = relationship("Group", uselist=False)


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User)
