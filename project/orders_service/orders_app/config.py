from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DB_HOST:     str = "localhost"
    DB_PORT:     str = "5432"
    DB_NAME:     str = "appdb"
    DB_USER:     str = "postgres"
    DB_PASSWORD: str = "postgres"

    # ── JWT (shared secret with Auth service) ─────────────────────────────────
    JWT_SECRET:    str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"

    # ── Inter-service URLs ────────────────────────────────────────────────────
    ITEMS_SERVICE_URL: str = "http://localhost:8000"   # Items service base URL
    AUTH_SERVICE_URL:  str = "http://localhost:8001"   # Auth service base URL

    # ── App ───────────────────────────────────────────────────────────────────
    APP_NAME: str  = "Orders Service"
    DEBUG:    bool = False

    class Config:
        env_file = ".env"
        extra    = "ignore"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?options=-c search_path=orders,public"
        )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
