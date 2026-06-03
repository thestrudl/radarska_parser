"""Centralized configuration loaded from environment variables.

Replaces the hardcoded DB credentials that used to live in ``radar_main.py``.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    postgres_user: str = "radar"
    postgres_password: str = "radar_password"
    postgres_db: str = "radar"
    db_host: str = "db"
    db_port: int = 5432

    # Ingestion
    ingest_interval_minutes: int = 10
    grid_cell_pixels: int = 4

    # External sources
    radar_image_url: str = (
        "https://meteo.arso.gov.si/uploads/probase/www/observ/radar/si0-rm.gif"
    )
    weather_xml_url: str = (
        "https://meteo.arso.gov.si/uploads/probase/www/observ/surface/"
        "text/sl/observation_si_latest.xml"
    )

    # Storage
    frames_dir: str = "/data/frames"

    # Geocoding
    nominatim_user_agent: str = "radarska-parser"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.db_host}:{self.db_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
