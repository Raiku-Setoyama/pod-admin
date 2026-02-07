"""Application configuration settings."""

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "POD Admin API"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str

    @property
    def async_database_url(self) -> str:
        """Convert standard PostgreSQL URL to asyncpg format."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY_SOURCES: dict[str, str] = {"dev-api-key": "DEV"}

    @property
    def API_KEYS(self) -> list[str]:
        """Get list of valid API keys."""
        return list(self.API_KEY_SOURCES.keys())

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB


settings = Settings()
