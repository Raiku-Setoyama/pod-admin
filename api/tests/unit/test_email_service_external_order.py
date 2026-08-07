"""Unit tests for EmailService.send_external_order_notification().

SendGrid client is mocked. Covers success/failure/exception handling,
subject, multiple recipients, and plain-text body building (incl. admin link).
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.fixture
def email_service() -> Iterator[tuple[Any, ...]]:
    """Create EmailService with a mocked SendGrid client (no admin link)."""
    with patch("app.services.email_service.SendGridAPIClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        service = EmailService(
            api_key="test-api-key",
            from_email="from@example.com",
            contact_email="support@example.com",
        )
        yield service, mock_client


@pytest.fixture
def sample_order_items() -> list[Any]:
    return [
        {"product_name": "オリジナルTシャツ", "quantity": 2},
        {"product_name": "アクリルキーホルダー", "quantity": 1},
    ]


ORDERED_AT = datetime(2026, 6, 28, 3, 0, tzinfo=UTC)  # JST 12:00


class TestSendExternalOrderNotification:
    @pytest.mark.asyncio
    async def test_successful_send_to_multiple_recipients(
        self, email_service: tuple[Any, ...], sample_order_items: list[Any]
    ) -> None:
        service, mock_client = email_service
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        result = await service.send_external_order_notification(
            to_emails=["a@example.com", "b@example.com"],
            order_number="0000001",
            source_code="RKSYO",
            ordered_at=ORDERED_AT,
            customer_name="山田太郎",
            order_items=sample_order_items,
            total_price=5000,
            order_id="order-1",
        )

        assert result is True
        mock_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_status_returns_false(self, email_service: tuple[Any, ...], sample_order_items: list[Any]) -> None:
        service, mock_client = email_service
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client.send.return_value = mock_response

        result = await service.send_external_order_notification(
            to_emails=["a@example.com"],
            order_number="0000001",
            source_code="RKSYO",
            ordered_at=ORDERED_AT,
            customer_name="山田太郎",
            order_items=sample_order_items,
            total_price=5000,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_exception_returns_false(self, email_service: tuple[Any, ...], sample_order_items: list[Any]) -> None:
        service, mock_client = email_service
        mock_client.send.side_effect = Exception("network error")

        result = await service.send_external_order_notification(
            to_emails=["a@example.com"],
            order_number="0000001",
            source_code="RKSYO",
            ordered_at=ORDERED_AT,
            customer_name="山田太郎",
            order_items=sample_order_items,
            total_price=5000,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_subject_contains_order_number(
        self, email_service: tuple[Any, ...], sample_order_items: list[Any]
    ) -> None:
        service, mock_client = email_service
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        await service.send_external_order_notification(
            to_emails=["a@example.com"],
            order_number="0000042",
            source_code="RKSYO",
            ordered_at=ORDERED_AT,
            customer_name="山田太郎",
            order_items=sample_order_items,
            total_price=5000,
        )

        mail_message = mock_client.send.call_args[0][0]
        assert "0000042" in mail_message.subject.get()


class TestBuildExternalOrderText:
    def _service(self, admin_base_url: str = "") -> EmailService:
        with patch("app.services.email_service.SendGridAPIClient"):
            return EmailService(
                api_key="test",
                from_email="from@example.com",
                contact_email="support@example.com",
                admin_base_url=admin_base_url,
            )

    def test_text_contains_order_info(self) -> None:
        service = self._service()
        text = service._build_external_order_text(
            order_number="0000001",
            source_code="RKSYO",
            ordered_at="2026-06-28 12:00",
            customer_name="山田太郎",
            order_items=[{"product_name": "オリジナルTシャツ", "quantity": 2}],
            total_price="5,000",
            order_detail_url=None,
        )

        assert "0000001" in text
        assert "RKSYO" in text
        assert "2026-06-28 12:00" in text
        assert "山田太郎" in text
        assert "オリジナルTシャツ" in text
        assert "x 2" in text
        assert "5,000円" in text

    def test_text_includes_link_when_provided(self) -> None:
        service = self._service()
        text = service._build_external_order_text(
            order_number="0000001",
            source_code="RKSYO",
            ordered_at="2026-06-28 12:00",
            customer_name="山田太郎",
            order_items=[{"product_name": "Tシャツ", "quantity": 1}],
            total_price="2,500",
            order_detail_url="https://admin.example.com/orders/order-1",
        )

        assert "https://admin.example.com/orders/order-1" in text

    def test_text_omits_link_when_absent(self) -> None:
        service = self._service()
        text = service._build_external_order_text(
            order_number="0000001",
            source_code="RKSYO",
            ordered_at="2026-06-28 12:00",
            customer_name="山田太郎",
            order_items=[{"product_name": "Tシャツ", "quantity": 1}],
            total_price="2,500",
            order_detail_url=None,
        )

        assert "注文詳細" not in text

    @pytest.mark.asyncio
    async def test_admin_link_built_from_base_url(self, sample_order_items: list[Any]) -> None:
        service = self._service(admin_base_url="https://admin.example.com/")
        with patch.object(
            service, "_build_external_order_text", wraps=service._build_external_order_text
        ) as spy:
            with patch.object(service._client, "send") as mock_send:
                mock_send.return_value = MagicMock(status_code=202)
                await service.send_external_order_notification(
                    to_emails=["a@example.com"],
                    order_number="0000001",
                    source_code="RKSYO",
                    ordered_at=ORDERED_AT,
                    customer_name="山田太郎",
                    order_items=sample_order_items,
                    total_price=5000,
                    order_id="order-1",
                )

        # 末尾スラッシュは正規化され、/orders/{id} が付与される
        assert (
            spy.call_args.kwargs["order_detail_url"]
            == "https://admin.example.com/orders/order-1"
        )
