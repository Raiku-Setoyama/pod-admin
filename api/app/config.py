"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # BaseSettings の設定は SettingsConfigDict を使う。
    # pydantic の ConfigDict には env_file / case_sensitive のキーがない。
    model_config = SettingsConfigDict(
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

    # 接続プール。1 インスタンスあたり DB_POOL_SIZE + DB_MAX_OVERFLOW 本まで接続を開く。
    # コンテナ実行基盤では「インスタンス数 × この値」が DB の max_connections を超えないよう、
    # 環境ごとに絞る（小さいインスタンスの DB は max_connections も小さい）。
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

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

    # File Storage (GCS) — ローカル/本番ともに GCS でファイル永続化
    # Railway のローカルディスクは再デプロイで消えるため、製造データ/チャット添付/出荷
    # ファイルを GCS に永続化する。ローカル開発も本番と同様に GCS を使い、バケットは
    # 本番と分ける（例: prod / dev）。GCS_BUCKET が空の場合のみローカル保存へ
    # フォールバックする（CI/オフライン用）。
    GCS_BUCKET: str = ""
    # サービスアカウント鍵JSON文字列（Railway シークレット想定）。空なら ADC へフォールバック。
    GCS_CREDENTIALS_JSON: str = ""
    # バケット内のキー前置（任意の名前空間。例: "prod"）。DBの file_path は非依存のまま。
    GCS_PREFIX: str = ""

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

    # メーカーポータルのログインURL（メーカー日次発注通知メールに記載）
    MANUFACTURER_LOGIN_URL: str = "https://pod-admin-beige.vercel.app/manufacturer-login"

    # 内部エンドポイント（メーカー日次発注ダイジェスト）の共有シークレット。
    # 未設定なら内部エンドポイントは無効（403）。外部トリガ(cron等)から X-Internal-Secret で認証する。
    INTERNAL_API_SECRET: str = ""

    # 製造データ生成ワーカー（app/worker.py）
    # 1 回の起動で処理を続ける上限秒数。超えたら残りは次回の起動に委ねる。
    # 実行基盤側のタスクタイムアウトより十分に短くしておくこと（途中で殺されると
    # 生成中の行が宙吊りになり、次回の起動が復旧するまで待たされる）。
    WORKER_MAX_RUNTIME_SECONDS: float = 3000.0
    # 1 回の起動で処理する件数の上限。0 以下なら件数では打ち切らない。
    WORKER_MAX_ITEMS: int = 50


settings = Settings()
