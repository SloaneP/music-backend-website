from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import CreateSchema
from typing import AsyncGenerator
from ..config import load_config
import logging

cfg = load_config()
logger = logging.getLogger(cfg.SERVICE_NAME)

class Database_Initializer():
    def __init__(self, base, schema):
        self.base = base
        self.schema = schema
        self.__async_session_maker = None

    def get_schema(self):
        return self.schema

    async def init_db(self, postgre_dsn):
        engine = create_async_engine(postgre_dsn)
        self.__async_session_maker = async_sessionmaker(
            engine, expire_on_commit=False
        )

        async with engine.begin() as connection:
            schema = self.get_schema()

            def check_schema(conn):
                return inspect(conn).has_schema(schema)

            if not (await connection.run_sync(check_schema)):
                await connection.execute(CreateSchema(schema))

            await connection.run_sync(self.base.metadata.create_all)
            await connection.commit()

        logger.info("DB initialized and committed.")

    @property
    def async_session_maker(self):
        if self.__async_session_maker is None:
            raise Exception("Database session maker is not initialized.")
        return self.__async_session_maker


SCHEMA = "analytics"
Base = declarative_base()
db_initializer = Database_Initializer(Base, SCHEMA)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with db_initializer.async_session_maker() as session:
        yield session

