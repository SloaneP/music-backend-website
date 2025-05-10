from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import CreateSchema
from typing import AsyncGenerator

SCHEMA = "user"
Base = declarative_base()

class DatabaseInitializer:
    def __init__(self, base, schema: str):
        self.base = base
        self.schema = schema
        self.__async_session_maker = None

    def get_schema(self) -> str:
        return self.schema

    async def init_db(self, db_url: str):
        engine = create_async_engine(db_url, echo=True)
        self.__async_session_maker = async_sessionmaker(
            bind=engine,
            expire_on_commit=False
        )

        async with engine.begin() as conn:
            schema = self.get_schema()

            if not await self._check_schema(conn, schema):
                await self._create_schema(conn, schema)

            await conn.run_sync(self.base.metadata.create_all)

    async def _check_schema(self, conn, schema: str) -> bool:
        return await conn.run_sync(lambda conn: inspect(conn).has_schema(schema))

    async def _create_schema(self, conn, schema: str):
        await conn.execute(CreateSchema(schema))

    @property
    def async_session_maker(self) -> async_sessionmaker:
        return self.__async_session_maker

db_initializer = DatabaseInitializer(Base, SCHEMA)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with db_initializer.async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
