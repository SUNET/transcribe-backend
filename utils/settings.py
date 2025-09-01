import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import field_validator


class Settings(BaseSettings):
    """
    Settings for the application.
    """

    @field_validator("OIDC_SCOPE", mode="before")
    @classmethod
    def decode_scope(cls, v: str) -> list[str]:
        return [str(x) for x in v.split(",")]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
        enable_decoding=False,
    )

    API_DATABASE_URL: str = "sqlite:///jobs.db"
    API_DEBUG: bool = True
    API_DESCRIPTION: str = "A REST API for the Whisper ASR model"
    API_FILE_STORAGE_DIR: str = ""
    API_PREFIX: str = "/api/v1"
    API_SECRET_KEY: str = ""
    API_TITLE: str = "Whisper REST backend"
    API_VERSION: str = "0.1.0"
    API_WORKER_CLIENT_DN = "CN=TranscriberWorker,O=SUNET,ST=Stockholm,C=SE"

    # OIDC configuration.
    OIDC_CLIENT_ID: str = ""
    OIDC_SCOPE: list[str] = []
    OIDC_CLIENT_SECRET: str = ""
    OIDC_METADATA_URL: str = ""
    OIDC_REDIRECT_URI: str = ""
    OIDC_REFRESH_URI: str = ""
    OIDC_FRONTEND_URI: str = ""


@lru_cache
def get_settings() -> Settings:
    """
    Get the settings for the application.
    """
    if not os.path.exists(Settings().API_FILE_STORAGE_DIR):
        os.makedirs(Settings().API_FILE_STORAGE_DIR)

    return Settings()
