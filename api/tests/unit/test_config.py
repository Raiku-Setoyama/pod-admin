"""Test configuration settings."""

import os


def test_settings_defaults():
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


def test_settings_environment_override():
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


def test_settings_cors_origins():
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
