from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────────────────────
    DB_HOST:     str = "localhost"
    DB_PORT:     str = "5432"
    DB_NAME:     str = "appdb"
    DB_USER:     str = "postgres"
    DB_PASSWORD: str = "postgres"

    # ── JWT ──────────────────────────────────────────────────────────────────
    JWT_SECRET:    str = "change-me-in-production-use-a-long-random-string"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES:  int = 60        # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS:    int = 7

    # ── OTP ──────────────────────────────────────────────────────────────────
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH:         int = 6

    # ── Email (Gmail SMTP via App Password) ──────────────────────────────────
    SMTP_HOST:     str  = "smtp.gmail.com"
    SMTP_PORT:     int  = 587
    SMTP_USER:     str  = ""           # set in .env
    SMTP_PASSWORD: str  = ""           # set in .env  (Gmail App Password)
    EMAIL_FROM:    str  = ""           # defaults to SMTP_USER if empty
    EMAIL_ENABLED: bool = True         # set False to skip emails in dev/test

    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Auth Service"
    DEBUG:    bool = False

    class Config:
        env_file = ".env"
        extra    = "ignore"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?options=-c search_path=auth,public"
        )

    @property
    def sender_email(self) -> str:
        return self.EMAIL_FROM or self.SMTP_USER


@lru_cache()
def get_settings() -> Settings:
    return Settings()
