from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, Extra, AmqpDsn

class Config(BaseSettings):

    PG_ASYNC_DSN: PostgresDsn = Field(
        default='postgresql+asyncpg://postgres:postgres@postgresql:5432/postgres',
        env='PG_ASYNC_DSN',
        alias='PG_ASYNC_DSN'
    )

    FRONT: str = Field(
        default='http://localhost:5173',
        env='FRONT',
        alias='FRONT'
    )

    JWT_SECRET: str = Field(
        default='JWT_SECRET',
        env='JWT_SECRET',
        alias='JWT_SECRET'
    )

    SERVICE_NAME: str = "RecommendationService"

    class Config:
        env_file = ".env"
        extra = Extra.allow


def load_config() -> Config:
    return Config()
