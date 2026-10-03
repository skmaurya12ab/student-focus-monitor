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
    
    # Google OAuth 2.0 / OpenID Connect
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:5173/auth/callback"
    
    # JWT & Session Security
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production-sfm-2026"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
