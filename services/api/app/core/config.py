from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Пилотный контур передаёт секреты файлами (docker secrets), а не переменными окружения.
SECRETS_DIR = Path("/run/secrets")


class Settings(BaseSettings):
    """Настройки из переменных окружения (см. ``.env.example``)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./brigadir.db"
    cors_origins: str = "http://localhost:8081,http://127.0.0.1:8081"
    demo_session_ttl_hours: int = Field(default=24, ge=1, le=24 * 7)
    user_session_ttl_hours: int = Field(default=24 * 30, ge=1, le=24 * 90)
    log_level: str = "INFO"
    # demo — синтетические профили и учебный банк; pilot — вход по коду участника,
    # демо-эндпоинты и мок банка выключены (раздел 16.2, спринт 3).
    app_mode: Literal["demo", "pilot"] = "demo"
    pilot_terms_version: str = Field(default="pilot-2026-12", max_length=32)
    pilot_session_ttl_hours: int = Field(default=24 * 7, ge=1, le=24 * 30)
    # Журнал удалений вне БД: после восстановления бэкапа удаления применяются повторно (25).
    erasure_log_path: str | None = None
    # Живой учебный аккаунт (ADR-0007): реальных секунд на виртуальный день и запас
    # синтетического будущего, который раскрывается по мере хода времени.
    live_seconds_per_day: int = Field(default=45, ge=5, le=3600)
    live_horizon_days: int = Field(default=120, ge=14, le=120)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    if SECRETS_DIR.is_dir():
        return Settings(_secrets_dir=SECRETS_DIR)
    return Settings()
