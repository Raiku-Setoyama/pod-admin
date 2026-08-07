"""Order image download service.

FEAT-0018: 受注イメージ画像ZIPダウンロード
"""

import asyncio
import logging
import mimetypes
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

from app.repositories.order_repository import OrderRepository
from app.utils.zip_builder import ZipBuilder

logger = logging.getLogger(__name__)


class OrderImageService:
    """Service for downloading order images and building ZIP files."""

    def __init__(self, order_repo: OrderRepository):
        self._order_repo = order_repo

    async def collect_and_build_zip(
        self, order_ids: list[str]
    ) -> bytes:
        """Collect design images from orders and build a ZIP file.

        Args:
            order_ids: List of order IDs to collect images from.

        Returns:
            ZIP file content as bytes.

        Raises:
            HTTPException: 404 if no images could be collected.
        """
        # Collect image URLs with metadata from orders
        image_tasks: list[dict[str, Any]] = []

        for order_id in order_ids:
            order = await self._order_repo.find_by_id(order_id)
            if order is None:
                logger.warning(f"Order not found: {order_id}")
                continue

            item_counter = 0
            for item in order.items:
                if item.design_image_url is None:
                    continue
                item_counter += 1
                image_tasks.append({
                    "order_number": order.order_number,
                    "product_name": item.product_name,
                    "design_image_url": item.design_image_url,
                    "index": item_counter,
                })

        if not image_tasks:
            raise HTTPException(
                status_code=404,
                detail="ダウンロード対象の画像がありません",
            )

        # Fetch images in parallel with semaphore
        semaphore = asyncio.Semaphore(10)
        fetched_images: list[dict[str, Any] | None] = []

        async with httpx.AsyncClient() as client:

            async def fetch_image(task: dict[str, Any]) -> dict[str, Any] | None:
                async with semaphore:
                    try:
                        response = await client.get(task["design_image_url"])
                        if response.status_code != 200:
                            logger.warning(
                                f"Failed to fetch image: {task['design_image_url']} "
                                f"(status={response.status_code})"
                            )
                            return None

                        # Determine file extension
                        ext = self._get_extension_from_url(task["design_image_url"])
                        if not ext:
                            ext = self._get_extension_from_content_type(
                                response.headers.get("content-type", "")
                            )
                        if not ext:
                            ext = ".png"

                        return {
                            "order_number": task["order_number"],
                            "product_name": task["product_name"],
                            "index": task["index"],
                            "content": response.content,
                            "extension": ext,
                        }
                    except Exception as e:
                        logger.warning(
                            f"Error fetching image {task['design_image_url']}: {e}"
                        )
                        return None

            results = await asyncio.gather(
                *[fetch_image(task) for task in image_tasks]
            )
            fetched_images = [r for r in results if r is not None]

        if not fetched_images:
            raise HTTPException(
                status_code=404,
                detail="全ての画像の取得に失敗しました",
            )

        # Build ZIP
        builder = ZipBuilder()
        for img in fetched_images:
            file_path = (
                f"{img['order_number']}/"
                f"{img['product_name']}_{img['index']}{img['extension']}"
            )
            builder.add_file(file_path, img["content"])

        return builder.build()

    def generate_zip_filename(self) -> str:
        """Generate ZIP filename with timestamp.

        Returns:
            Filename in format: 受注画像_{YYYYMMDD_HHMMSS}.zip
        """
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        return f"受注画像_{timestamp}.zip"

    @staticmethod
    def _get_extension_from_url(url: str) -> str | None:
        """Extract file extension from URL path."""
        parsed = urlparse(url)
        path = parsed.path
        if "." in path:
            ext = path.rsplit(".", 1)[-1].lower()
            if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "tiff"):
                return f".{ext}"
        return None

    @staticmethod
    def _get_extension_from_content_type(content_type: str) -> str | None:
        """Get file extension from Content-Type header."""
        if not content_type:
            return None
        # Remove parameters (e.g., "image/jpeg; charset=utf-8")
        mime_type = content_type.split(";")[0].strip().lower()

        # Map common image MIME types to extensions
        mime_map = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
            "image/svg+xml": ".svg",
            "image/tiff": ".tiff",
        }

        ext = mime_map.get(mime_type)
        if ext:
            return ext

        # Fallback to mimetypes module
        guessed_ext = mimetypes.guess_extension(mime_type)
        if guessed_ext and guessed_ext != ".bin":
            return guessed_ext

        return None
