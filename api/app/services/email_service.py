"""Email service for sending notifications via SendGrid."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, From, To

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


class EmailService:
    """SendGrid-based email sending service."""

    def __init__(self, api_key: str, from_email: str, contact_email: str):
        self._client = SendGridAPIClient(api_key)
        self._from_email = from_email
        self._contact_email = contact_email
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
        )

    async def send_shipping_notification(
        self,
        to_email: str,
        customer_name: str,
        tracking_number: str,
        carrier_name: str,
        order_external_id: str,
        order_items: list[dict],
    ) -> bool:
        """Send shipping notification email.

        Args:
            to_email: Recipient email address.
            customer_name: Customer name for greeting.
            tracking_number: Tracking number for the shipment.
            carrier_name: Carrier/shipping company name.
            order_external_id: External order number.
            order_items: List of dicts with product_name, quantity, thumbnail_image_url.

        Returns:
            True if sent successfully, False otherwise. Never raises exceptions.
        """
        try:
            subject = "【RKSYO】ご注文商品を発送いたしました"

            # Render HTML template
            template = self._jinja_env.get_template("shipping_notification.html")
            html_content = template.render(
                customer_name=customer_name,
                tracking_number=tracking_number,
                carrier_name=carrier_name,
                order_external_id=order_external_id,
                order_items=order_items,
                contact_email=self._contact_email,
            )

            # Build plain text version
            text_content = self._build_text_content(
                customer_name=customer_name,
                tracking_number=tracking_number,
                carrier_name=carrier_name,
                order_external_id=order_external_id,
                order_items=order_items,
            )

            message = Mail(
                from_email=From(self._from_email),
                to_emails=To(to_email),
                subject=subject,
            )
            message.content = [
                Content("text/plain", text_content),
                Content("text/html", html_content),
            ]

            # SendGrid SDK is synchronous, wrap in thread
            response = await asyncio.to_thread(self._client.send, message)

            if response.status_code in (200, 201, 202):
                logger.info(
                    f"Shipping notification sent to {to_email} for order {order_external_id}"
                )
                return True
            else:
                logger.warning(
                    f"SendGrid returned status {response.status_code} "
                    f"for order {order_external_id} to {to_email}"
                )
                return False

        except Exception:
            logger.exception(
                f"Failed to send shipping notification to {to_email} "
                f"for order {order_external_id}"
            )
            return False

    def _build_text_content(
        self,
        customer_name: str,
        tracking_number: str,
        carrier_name: str,
        order_external_id: str,
        order_items: list[dict],
    ) -> str:
        """Build plain text email content."""
        items_text = "\n".join(
            f"  - {item['product_name']} x {item['quantity']}"
            for item in order_items
        )

        return f"""{customer_name} 様

いつもご愛顧いただきありがとうございます。
ご注文いただいた商品を発送いたしました。追跡番号を使用し、配達状況をご確認いただけます｡

■ 注文番号: {order_external_id}
■ 運送会社: {carrier_name}
■ 伝票番号: {tracking_number}

■ 発送商品:
{items_text}

商品の到着まで今しばらくお待ちください。

ご不明な点がございましたら、下記までお問い合わせください。
{self._contact_email}

Center River
"""
