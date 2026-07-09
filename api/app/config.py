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

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "https://pod-admin-beige.vercel.app",
    ]

    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Email (SendGrid)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    CONTACT_EMAIL: str = ""

    # 管理画面のベースURL（受注通知メールの注文詳細リンク用、未設定ならリンクを描画しない）
    ADMIN_BASE_URL: str = ""

    # メーカーポータルのログインURL（メーカー日次発注通知メールに記載）
    MANUFACTURER_LOGIN_URL: str = "https://pod-admin-beige.vercel.app/manufacturer-login"

    # 内部エンドポイント（メーカー日次発注ダイジェスト）の共有シークレット。
    # 未設定なら内部エンドポイントは無効（403）。外部トリガ(cron等)から X-Internal-Secret で認証する。
    INTERNAL_API_SECRET: str = ""


settings = Settings()
