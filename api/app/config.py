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
    API_V2_PREFIX: str = "/api/v2"
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

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://pod-admin-beige.vercel.app",
    ]

    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Storage backend ("local" ローカルFS / "gcs" Google Cloud Storage)
    STORAGE_BACKEND: str = "local"
    GCS_BUCKET: str = ""
    GCS_PROJECT: str = ""

    # illustrator-vm (Product Manufacturing API) 連携
    # 空なら製造データ生成をスキップ（manufacturing_data は pending のまま）
    ILLUSTRATOR_VM_URL: str = ""
    ILLUSTRATOR_VM_TIMEOUT: float = 60.0
    ILLUSTRATOR_VM_POLL_INTERVAL: float = 3.0
    ILLUSTRATOR_VM_POLL_TIMEOUT: float = 360.0
    ILLUSTRATOR_VM_MAX_RETRIES: int = 3

    # Email (SendGrid)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    CONTACT_EMAIL: str = ""

    # 管理画面のベースURL（受注通知メールの注文詳細リンク用、未設定ならリンクを描画しない）
    ADMIN_BASE_URL: str = ""


settings = Settings()
