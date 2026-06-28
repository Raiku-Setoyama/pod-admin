"""Email service for sending notifications via SendGrid."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, From, Mail, To

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

JST = ZoneInfo("Asia/Tokyo")


class EmailService:
    """SendGrid-based email sending service."""

    def __init__(
        self,
        api_key: str,
        from_email: str,
        contact_email: str,
        admin_base_url: str = "",
    ):
        self._client = SendGridAPIClient(api_key)
        self._from_email = from_email
        self._contact_email = contact_email
        self._admin_base_url = admin_base_url
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

    async def send_external_order_notification(
        self,
        to_emails: list[str],
        order_number: str,
        source_code: str | None,
        ordered_at: datetime,
        customer_name: str,
        order_items: list[dict],
        total_price: int,
        order_id: str | None = None,
    ) -> bool:
        """Send a new-order notification to internal staff.

        外部販売サイト経由の受注を社内担当者へ知らせる通知メール。

        Args:
            to_emails: 通知先メールアドレス（複数可）。
            order_number: 受注番号。
            source_code: 販売サイトコード（OrderSource.code）。未設定なら None。
            ordered_at: 受注日時（tz-aware）。JST に変換して表示する。
            customer_name: 顧客名。
            order_items: product_name / quantity を持つ dict のリスト。
            total_price: 合計金額（円）。
            order_id: 管理画面の注文詳細リンク用ID（ADMIN_BASE_URL 設定時のみ使用）。

        Returns:
            True if sent successfully, False otherwise. Never raises exceptions.
        """
        try:
            subject = f"【新規受注】注文番号 {order_number} を受け付けました"

            ordered_at_jst = ordered_at.astimezone(JST).strftime("%Y-%m-%d %H:%M")
            total_price_str = f"{total_price:,}"
            order_detail_url = (
                f"{self._admin_base_url.rstrip('/')}/orders/{order_id}"
                if self._admin_base_url and order_id
                else None
            )

            template = self._jinja_env.get_template("external_order_notification.html")
            html_content = template.render(
                order_number=order_number,
                source_code=source_code,
                ordered_at=ordered_at_jst,
                customer_name=customer_name,
                order_items=order_items,
                total_price=total_price_str,
                order_detail_url=order_detail_url,
            )

            text_content = self._build_external_order_text(
                order_number=order_number,
                source_code=source_code,
                ordered_at=ordered_at_jst,
                customer_name=customer_name,
                order_items=order_items,
                total_price=total_price_str,
                order_detail_url=order_detail_url,
            )

            message = Mail(
                from_email=From(self._from_email),
                to_emails=[To(email) for email in to_emails],
                subject=subject,
            )
            message.content = [
                Content("text/plain", text_content),
                Content("text/html", html_content),
            ]

            response = await asyncio.to_thread(self._client.send, message)

            if response.status_code in (200, 201, 202):
                logger.info(
                    f"External order notification sent for order {order_number} "
                    f"to {len(to_emails)} recipient(s)"
                )
                return True
            else:
                logger.warning(
                    f"SendGrid returned status {response.status_code} "
                    f"for external order notification {order_number}"
                )
                return False

        except Exception:
            logger.exception(
                f"Failed to send external order notification for order {order_number}"
            )
            return False

    def _build_external_order_text(
        self,
        order_number: str,
        source_code: str | None,
        ordered_at: str,
        customer_name: str,
        order_items: list[dict],
        total_price: str,
        order_detail_url: str | None,
    ) -> str:
        """Build plain text content for the external order notification."""
        items_text = "\n".join(
            f"  - {item['product_name']} x {item['quantity']}"
            for item in order_items
        )
        link_text = (
            f"\n■ 注文詳細: {order_detail_url}\n" if order_detail_url else ""
        )

        return f"""外部販売サイトから新しい注文を受け付けました。

■ 注文番号: {order_number}
■ 販売サイト: {source_code or "-"}
■ 受注日時: {ordered_at}
■ 顧客名: {customer_name}

■ 注文商品:
{items_text}

■ 合計金額: {total_price}円
{link_text}
"""

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
