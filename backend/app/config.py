from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Testfoodo API"
    environment: str = "development"
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'testfoodo.db'}"
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    auto_create_schema: bool = True
    session_days: int = 30
    scraper_user_agent: str = (
        "Testfoodo/1.0 (UMD student nutrition tracker; educational use)"
    )
    scraper_concurrency: int = 6
    auto_refresh_menus: bool = True
    menu_refresh_minutes: int = 15
    menu_future_days: int = 7

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def allowed_origin_list(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
