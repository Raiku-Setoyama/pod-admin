"""Unit tests for EmailService.

Tests SendGrid email sending with mocked client,
template rendering, and error handling.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.services.email_service import EmailService


@pytest.fixture
def email_service():
    """Create EmailService with test config."""
    with patch("app.services.email_service.SendGridAPIClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        service = EmailService(
            api_key="test-api-key",
            from_email="test@example.com",
            contact_email="support@example.com",
        )
        yield service, mock_client


@pytest.fixture
def sample_order_items():
    """Sample order items for testing."""
    return [
        {
            "product_name": "アクリルキーホルダー",
            "quantity": 2,
            "thumbnail_image_url": "https://example.com/thumb1.png",
        },
        {
            "product_name": "ステッカー",
            "quantity": 1,
            "thumbnail_image_url": None,
        },
    ]


class TestEmailServiceSendShippingNotification:
    """Test EmailService.send_shipping_notification()."""

    @pytest.mark.asyncio
    async def test_successful_send(self, email_service, sample_order_items):
        """SendGrid returns 202 -> returns True."""
        service, mock_client = email_service

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        result = await service.send_shipping_notification(
            to_email="customer@example.com",
            customer_name="テスト顧客",
            tracking_number="1234-5678-9012",
            carrier_name="ヤマト運輸",
            order_external_id="ORD-0001",
            order_items=sample_order_items,
        )

        assert result is True
        mock_client.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_sendgrid_error_status_returns_false(self, email_service, sample_order_items):
        """SendGrid returns non-success status -> returns False."""
        service, mock_client = email_service

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_client.send.return_value = mock_response

        result = await service.send_shipping_notification(
            to_email="customer@example.com",
            customer_name="テスト顧客",
            tracking_number="1234-5678-9012",
            carrier_name="ヤマト運輸",
            order_external_id="ORD-0001",
            order_items=sample_order_items,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_sendgrid_exception_returns_false(self, email_service, sample_order_items):
        """SendGrid raises exception -> returns False (never propagates)."""
        service, mock_client = email_service

        mock_client.send.side_effect = Exception("Network error")

        result = await service.send_shipping_notification(
            to_email="customer@example.com",
            customer_name="テスト顧客",
            tracking_number="1234-5678-9012",
            carrier_name="ヤマト運輸",
            order_external_id="ORD-0001",
            order_items=sample_order_items,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_mail_message_has_correct_subject(self, email_service, sample_order_items):
        """Mail message has correct Japanese subject line."""
        service, mock_client = email_service

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_client.send.return_value = mock_response

        await service.send_shipping_notification(
            to_email="customer@example.com",
            customer_name="テスト顧客",
            tracking_number="1234-5678-9012",
            carrier_name="ヤマト運輸",
            order_external_id="ORD-0001",
            order_items=sample_order_items,
        )

        call_args = mock_client.send.call_args
        mail_message = call_args[0][0]
        assert mail_message.subject.get() == "【Center River】ご注文商品を発送いたしました"

    @pytest.mark.asyncio
    async def test_status_200_returns_true(self, email_service, sample_order_items):
        """SendGrid returns 200 -> returns True."""
        service, mock_client = email_service

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.send.return_value = mock_response

        result = await service.send_shipping_notification(
            to_email="customer@example.com",
            customer_name="テスト顧客",
            tracking_number="1234-5678-9012",
            carrier_name="ヤマト運輸",
            order_external_id="ORD-0001",
            order_items=sample_order_items,
        )

        assert result is True


class TestEmailServiceBuildTextContent:
    """Test EmailService._build_text_content()."""

    def test_text_content_contains_order_info(self):
        """Plain text content includes all key information."""
        with patch("app.services.email_service.SendGridAPIClient"):
            service = EmailService(
                api_key="test",
                from_email="test@example.com",
                contact_email="support@example.com",
            )

        text = service._build_text_content(
            customer_name="テスト顧客",
            tracking_number="1234-5678-9012",
            carrier_name="ヤマト運輸",
            order_external_id="ORD-0001",
            order_items=[
                {"product_name": "アクリルキーホルダー", "quantity": 2},
            ],
        )

        assert "テスト顧客" in text
        assert "1234-5678-9012" in text
        assert "ヤマト運輸" in text
        assert "ORD-0001" in text
        assert "アクリルキーホルダー" in text
        assert "x 2" in text
        assert "support@example.com" in text
