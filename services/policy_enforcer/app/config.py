from typing import Tuple, Type

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource
from pydantic import Field, FilePath, SecretStr

class Config(BaseSettings):
    jwt_secret: SecretStr = Field(
        alias='JWT_SECRET'
    )

    FRONT: str = Field(
        default='http://localhost:5173',
        env='FRONT',
        alias='FRONT'
    )

    policies_config_path: FilePath = Field(
        default='policies.yaml',
        alias='POLICIES_CONFIG_PATH'
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return dotenv_settings, env_settings, init_settings

def load_config(*arg, **vararg) -> Config:
    return Config(*arg, **vararg)