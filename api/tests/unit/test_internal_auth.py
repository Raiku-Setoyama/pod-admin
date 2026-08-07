"""Unit tests for the internal shared-secret auth dependency."""

import pytest

from app.config import settings as app_settings
from app.dependencies import verify_internal_secret
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
