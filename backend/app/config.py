from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://eventapp:eventapp_dev@localhost:5432/eventapp"
    redis_url: str = "redis://localhost:6379/0"
    environment: str = "development"

    # API settings
    api_prefix: str = "/api"
    page_size: int = 20
    max_page_size: int = 100

    # Bangkok coordinates (center)
    default_lat: float = 13.7563
    default_lng: float = 100.5018
    default_radius_km: float = 10.0

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
