from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, Field, Extra, SecretStr, FilePath


class Config(BaseSettings):
    PG_ASYNC_DSN: PostgresDsn = Field(
        default='postgresql+asyncpg://postgres:postgres@postgresql:5432/postgres',
        env='PG_ASYNC_DSN',
        alias='PG_ASYNC_DSN'
    )

    FRONT: str = Field(
        default='http://localhost:3000',
        env='FRONT',
        alias='FRONT'
    )

    default_groups_config_path: FilePath = Field(
        default='/mnt/default-groups.json',
        env='DEFAULT_GROUPS_CONFIG_PATH',
        alias='DEFAULT_GROUPS_CONFIG_PATH'
    )

    jwt_secret: SecretStr = Field(
        default=None,
        env='JWT_SECRET',
        alias='JWT_SECRET'
    )

    reset_password_token_secret: SecretStr = Field(
        default='RESET_PASSWORD_TOKEN_SECRET',
        env='RESET_PASSWORD_TOKEN_SECRET',
        alias='RESET_PASSWORD_TOKEN_SECRET'
    )

    verification_token_secret: SecretStr = Field(
        default='VERIFICATION_TOKEN_SECRET',
        env='VERIFICATION_TOKEN_SECRET',
        alias='VERIFICATION_TOKEN_SECRET'
    )

    class Config:
        env_file = ".env"
        extra = Extra.allow


def load_config() -> Config:
    return Config()