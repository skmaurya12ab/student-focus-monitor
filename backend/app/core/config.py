"""Application configuration settings using pydantic-settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings loaded from environment variables or defaults."""

    APP_ENV: str = "development"
    PROJECT_NAME: str = "Student Focus Monitor"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/student_focus_monitor"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
