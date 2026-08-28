"""Test configuration settings."""

import os


def test_settings_defaults() -> None:
    """Test default settings values."""
    from app.config import Settings

    # _env_file=Noneを渡して.envファイルを読み込まないようにする
    # DEBUG=Falseを明示的に渡して環境変数の影響を受けないようにする
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/testdb",
        SECRET_KEY="test-secret-key-for-testing-only",
        DEBUG=False,
        _env_file=None,
    )

    assert settings.PROJECT_NAME == "POD Admin API"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DEBUG is False


def test_settings_environment_override() -> None:
    """Test settings can be overridden via environment variables."""
    os.environ["PROJECT_NAME"] = "Custom API Name"
    os.environ["DEBUG"] = "true"
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/testdb"
    os.environ["SECRET_KEY"] = "test-secret-key"

    from app.config import Settings

    settings = Settings(_env_file=None)
    assert settings.PROJECT_NAME == "Custom API Name"
    assert settings.DEBUG is True

    # Cleanup
    del os.environ["PROJECT_NAME"]
    del os.environ["DEBUG"]
    del os.environ["DATABASE_URL"]
    del os.environ["SECRET_KEY"]


def test_settings_cors_origins() -> None:
    """Test CORS origins are properly parsed."""
    from app.config import Settings

    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/testdb",
        SECRET_KEY="test-secret-key",
        CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"],
        _env_file=None,
    )

    assert "http://localhost:3000" in settings.CORS_ORIGINS
    assert "http://localhost:8080" in settings.CORS_ORIGINS


def test_generation_worst_case_seconds_matches_infra_copy() -> None:
    """生成の最悪値が、Terraform に写した定数と一致することを固定する.

    `infra/envs/staging/main.tf` の `local.generation_worst_case_seconds` は
    この値の写しであり、そこから製造データ生成ワーカー（Cloud Run Job）の
    タイムアウトを導出している。Terraform は Python を読めないので、
    **ずれても何も壊れず、Job が生成の途中で殺されるという形でだけ現れる。**

    `ILLUSTRATOR_VM_*` を変えてこのテストが落ちたら、infra 側の定数も直すこと。
    """
    from app.config import Settings

    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost:5432/testdb",
        SECRET_KEY="test-secret-key",
        _env_file=None,
    )

    assert settings.generation_worst_case_seconds == 921
