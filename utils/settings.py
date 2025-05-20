import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Settings for the application.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        validate_assignment=True,
    )

    DATABASE_URL: str = "sqlite:///jobs.db"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    API_VERSION: str = "0.1.0"
    API_TITLE: str = "Whisper REST backend"
    API_DESCRIPTION: str = "A REST API for the Whisper ASR model"
    API_FILE_UPLOAD_DIR: str = ""
    API_FILE_STORAGE_DIR: str = ""
    OIDC_METADATA_URL: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: str = ""


@lru_cache
def get_settings() -> Settings:
    """
    Get the settings for the application.
    """
    if not os.path.exists(Settings().API_FILE_UPLOAD_DIR):
        os.makedirs(Settings().API_FILE_UPLOAD_DIR)
    if not os.path.exists(Settings().API_FILE_STORAGE_DIR):
        os.makedirs(Settings().API_FILE_STORAGE_DIR)

    return Settings()
