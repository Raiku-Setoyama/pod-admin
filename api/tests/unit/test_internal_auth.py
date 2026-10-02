"""Unit tests for the internal shared-secret auth dependencies.

ヘッダー版（X-Internal-Secret）と Basic 認証版（Cloud Monitoring の Webhook 用）は
同じ照合（_check_internal_secret）を通る。
"""

import pytest
from fastapi.security import HTTPBasicCredentials

from app.config import settings as app_settings
from app.dependencies import verify_internal_basic_auth, verify_internal_secret
from app.utils.exceptions import ForbiddenError, UnauthorizedError


class TestVerifyInternalSecret:
    @pytest.mark.asyncio
    async def test_forbidden_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "")
        with pytest.raises(ForbiddenError):
            await verify_internal_secret("anything")

    @pytest.mark.asyncio
    async def test_unauthorized_when_missing_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        with pytest.raises(UnauthorizedError):
            await verify_internal_secret(None)

    @pytest.mark.asyncio
    async def test_unauthorized_when_wrong(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        with pytest.raises(UnauthorizedError):
            await verify_internal_secret("wrong")

    @pytest.mark.asyncio
    async def test_passes_when_correct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        # 例外を送出しなければ OK
        await verify_internal_secret("s3cret")


def _basic(password: str) -> HTTPBasicCredentials:
    return HTTPBasicCredentials(username="monitoring", password=password)


class TestVerifyInternalBasicAuth:
    @pytest.mark.asyncio
    async def test_forbidden_when_unconfigured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "")
        with pytest.raises(ForbiddenError):
            await verify_internal_basic_auth(_basic("anything"))

    @pytest.mark.parametrize("credentials", [None, _basic("wrong"), _basic("")])
    @pytest.mark.asyncio
    async def test_unauthorized(
        self, monkeypatch: pytest.MonkeyPatch, credentials: HTTPBasicCredentials | None
    ) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        with pytest.raises(UnauthorizedError):
            await verify_internal_basic_auth(credentials)

    @pytest.mark.asyncio
    async def test_passes_on_password_match_regardless_of_username(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_settings, "INTERNAL_API_SECRET", "s3cret")
        await verify_internal_basic_auth(HTTPBasicCredentials(username="x", password="s3cret"))
