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

    # Email (SendGrid)
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""
    CONTACT_EMAIL: str = ""

    # 管理画面のベースURL（受注通知メールの注文詳細リンク用、未設定ならリンクを描画しない）
    ADMIN_BASE_URL: str = ""

    # illustrator-vm（Product Manufacturing API）
    # 未設定（空文字）の場合、製造データ生成クライアントは無効（None）となる。
    ILLUSTRATOR_VM_BASE_URL: str = ""
    # 認証ヘッダ（例: "Bearer xxx"）。VM は既定で認証なしのため通常は空でよい。
    ILLUSTRATOR_VM_AUTH_HEADER: str = ""
    # 1回の HTTP リクエストのタイムアウト秒（submit/status/download 個別）
    ILLUSTRATOR_VM_REQUEST_TIMEOUT: float = 60.0
    # ステータスポーリング間隔（秒）
    ILLUSTRATOR_VM_POLL_INTERVAL: float = 5.0
    # ジョブ完了待ちの最大秒数（VM は 1件最大約300秒）
    ILLUSTRATOR_VM_MAX_POLL_SECONDS: float = 360.0
    # 送信/取得の簡易リトライ回数（ネットワークエラー・503 時）
    ILLUSTRATOR_VM_MAX_RETRIES: int = 3

    # 外部注文 v2 の元データ画像取得（SSRF/DoS 防御）
    # 信頼して素通しするホスト名の許可リスト（例: ["assets.rksyo.com"]）。空なら
    # https 必須＋public IP のみ許可（内部・クラウドメタデータ宛を遮断）。内部アセット
    # サーバや dev スタブ（host.docker.internal 等）を使う場合はここに追加する。
    SOURCE_IMAGE_ALLOWED_HOSTS: list[str] = []
    # 1レイヤーあたりのダウンロード上限（バイト）。超過分は取得を中断してスキップ。
    SOURCE_IMAGE_MAX_BYTES: int = 25 * 1024 * 1024  # 25MB


settings = Settings()
