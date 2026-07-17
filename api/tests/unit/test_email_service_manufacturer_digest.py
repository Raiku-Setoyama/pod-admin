"""Unit tests for EmailService.send_manufacturer_daily_digest().

SendGrid client is mocked. Covers subject format (JST・2桁年・ゼロ埋めなし),
To/CC personalization, plain-text body (画像仕様準拠), and success/failure/exception.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.fixture
def email_service():
    """Create EmailService with a mocked SendGrid client."""
    with patch("app.services.email_service.SendGridAPIClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        service = EmailService(
            api_key="test-api-key",
            from_email="from@example.com",
            contact_email="support@example.com",
            manufacturer_login_url="https://pod-admin-beige.vercel.app/manufacturer-login",
        )
        yield service, mock_client


class TestSendManufacturerDailyDigest:
    @pytest.mark.asyncio
    async def test_successful_send_returns_true(self, email_service):
        service, mock_client = email_service
        mock_client.send.return_value = MagicMock(status_code=202)

        result = await service.send_manufacturer_daily_digest(
            to_emails=["a@example.com"],
            manufacturer_name="メーカーA",
            item_count=3,
            total_quantity=7,
            sent_date=date(2026, 6, 16),
        )

        assert result is True
        mock_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_subject_format_no_zero_pad(self, email_service):
        """件名: 【TOSYO__API発注依頼】{名}様{YY/M/D}（2桁年・月日ゼロ埋めなし）."""
        service, mock_client = email_service
        mock_client.send.return_value = MagicMock(status_code=202)

        await service.send_manufacturer_daily_digest(
            to_emails=["a@example.com"],
            manufacturer_name="メーカーA",
            item_count=1,
            total_quantity=1,
            sent_date=date(2026, 6, 16),
        )

        subject = mock_client.send.call_args[0][0].subject.get()
        assert subject == "【TOSYO__API発注依頼】メーカーA様26/6/16"

    @pytest.mark.asyncio
    async def test_subject_keeps_two_digit_month(self, email_service):
        service, mock_client = email_service
        mock_client.send.return_value = MagicMock(status_code=202)

        await service.send_manufacturer_daily_digest(
            to_emails=["a@example.com"],
            manufacturer_name="B社",
            item_count=1,
            total_quantity=1,
            sent_date=date(2026, 12, 5),
        )

        subject = mock_client.send.call_args[0][0].subject.get()
        assert subject == "【TOSYO__API発注依頼】B社様26/12/5"

    @pytest.mark.asyncio
    async def test_to_and_cc_personalization(self, email_service):
        service, mock_client = email_service
        mock_client.send.return_value = MagicMock(status_code=202)

        await service.send_manufacturer_daily_digest(
            to_emails=["to1@example.com", "to2@example.com"],
            manufacturer_name="メーカーA",
            item_count=2,
            total_quantity=5,
            cc_emails=["cc@example.com"],
            sent_date=date(2026, 6, 16),
        )

        personalization = mock_client.send.call_args[0][0].get()["personalizations"][0]
        assert personalization["to"] == [
            {"email": "to1@example.com"},
            {"email": "to2@example.com"},
        ]
        assert personalization["cc"] == [{"email": "cc@example.com"}]

    @pytest.mark.asyncio
    async def test_no_cc_when_empty(self, email_service):
        service, mock_client = email_service
        mock_client.send.return_value = MagicMock(status_code=202)

        await service.send_manufacturer_daily_digest(
            to_emails=["to@example.com"],
            manufacturer_name="メーカーA",
            item_count=1,
            total_quantity=1,
            sent_date=date(2026, 6, 16),
        )

        personalization = mock_client.send.call_args[0][0].get()["personalizations"][0]
        assert "cc" not in personalization

    @pytest.mark.asyncio
    async def test_error_status_returns_false(self, email_service):
        service, mock_client = email_service
        mock_client.send.return_value = MagicMock(status_code=500)

        result = await service.send_manufacturer_daily_digest(
            to_emails=["a@example.com"],
            manufacturer_name="メーカーA",
            item_count=1,
            total_quantity=1,
            sent_date=date(2026, 6, 16),
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, email_service):
        service, mock_client = email_service
        mock_client.send.side_effect = Exception("network error")

        result = await service.send_manufacturer_daily_digest(
            to_emails=["a@example.com"],
            manufacturer_name="メーカーA",
            item_count=1,
            total_quantity=1,
            sent_date=date(2026, 6, 16),
        )

        assert result is False


class TestBuildManufacturerDailyDigestText:
    def _service(self) -> EmailService:
        with patch("app.services.email_service.SendGridAPIClient"):
            return EmailService(
                api_key="test",
                from_email="from@example.com",
                contact_email="support@example.com",
                manufacturer_login_url="https://example.com/manufacturer-login",
            )

    def test_body_matches_spec(self):
        service = self._service()
        text = service._build_manufacturer_daily_digest_text(
            item_count=5,
            total_quantity=12,
            login_url="https://example.com/manufacturer-login",
        )

        assert "以下、発注済みの注文があります。" in text
        assert "発注中明細数　5 件" in text
        assert "合計数量　12 点" in text
        assert "https://example.com/manufacturer-login" in text
        assert "からログインしてご確認ください。" in text
