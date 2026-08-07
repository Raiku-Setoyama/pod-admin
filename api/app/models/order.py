"""Order model."""

import datetime as dt
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CustomerAddressMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.manufacturing_data import MfgDataStatus

if TYPE_CHECKING:
    from app.models.manufacturing_data import ManufacturingData
    from app.models.order_source import OrderSource
    from app.models.product import Product


class OrderStatus(str, Enum):
    """Order status."""

    PREPARING_ORDER = "preparing_order"  # 発注準備中（製造データ未準備。v2のみ経由）
    ORDERED = "ordered"  # 発注済み（製造データ準備完了 / v1は初期ステータス）
    MANUFACTURING = "manufacturing"  # 製造中
    DELIVERED = "delivered"  # 納入済み
    SHIPPED = "shipped"  # 発送完了（最終ステータス）
    CANCELLED = "cancelled"  # キャンセル済み


class OrderItemStatus(str, Enum):
    """OrderItem status - 製品単位のステータス.

    発注準備中 → 発注済み → 製造中 → 納入済み の統合ライフサイクル。
    発注準備中は製造データ（v2）が ready でない明細のみが取る（v1 は発注済みから開始）。
    キャンセル済みはライフサイクル外で、注文がキャンセルされた時に全明細が取る。
    """

    PREPARING_ORDER = "preparing_order"  # 発注準備中（製造データ未準備）
    ORDERED = "ordered"  # 発注済み（製造データ準備完了 / v1は初期ステータス）
    MANUFACTURING = "manufacturing"  # 製造中
    DELIVERED = "delivered"  # 納入済み
    CANCELLED = "cancelled"  # キャンセル済み（Order.cancelled から波及）


def item_status_for_manufacturing_ready(is_manufacturing_ready: bool) -> str:
    """製造データの ready 可否から、発注前ライフサイクル上の明細ステータスを返す.

    ready（= 製造データ不要な v1 明細を含む）なら「発注済み」、未 ready なら「発注準備中」。
    製造データの紐付け時（intake）と注文のキャンセル解除時で共有する。
    """
    if is_manufacturing_ready:
        return OrderItemStatus.ORDERED.value
    return OrderItemStatus.PREPARING_ORDER.value


def is_order_blocked_status(status: str, is_manufacturing_ready: bool) -> bool:
    """メーカー発注（→MANUFACTURING）できない明細か（ステータスと ready 可否から判定）.

    統合ステータスでは未 ready の明細は「発注準備中(preparing_order)」を取る。統合前
    データの防御として「発注済み(ordered) だが製造データ未 ready」も発注不可とする。
    OrderItem の property と、明細を行タプルで扱う発注資料生成の双方から共有する。
    """
    if status == OrderItemStatus.PREPARING_ORDER.value:
        return True
    return status == OrderItemStatus.ORDERED.value and not is_manufacturing_ready


class TshirtSize(str, Enum):
    """Tシャツサイズ."""

    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


class TshirtColor(str, Enum):
    """Tシャツカラー."""

    WHITE = "白"


class TshirtPosition(str, Enum):
    """Tシャツプリント位置."""

    FRONT = "正面"


# アクリルキーホルダー属性
class AcrylicKeychainSize(str, Enum):
    """アクリルキーホルダーサイズ."""

    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class AcrylicKeychainColor(str, Enum):
    """アクリルキーホルダーカラー."""

    ACRYLIC = "アクリル"


# アクリルスタンド属性
class AcrylicStandSize(str, Enum):
    """アクリルスタンドサイズ."""

    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class AcrylicStandColor(str, Enum):
    """アクリルスタンドカラー."""

    ACRYLIC = "アクリル"


# ステッカー属性
class StickerSize(str, Enum):
    """ステッカーサイズ."""

    MM50X50 = "50x50mm"
    MM70X70 = "70x70mm"
    MM100X100 = "100x100mm"


class StickerColor(str, Enum):
    """ステッカーカラー."""

    WHITE = "ホワイト"


# トートバッグ属性
class ToteBagSize(str, Enum):
    """トートバッグサイズ."""

    M = "M"


class ToteBagColor(str, Enum):
    """トートバッグカラー."""

    NATURAL = "ナチュラル"


class ToteBagPosition(str, Enum):
    """トートバッグプリント位置."""

    FRONT = "正面"


class Order(Base, UUIDPrimaryKeyMixin, CustomerAddressMixin, TimestampMixin):
    """Order model."""

    __tablename__ = "orders"

    # Order info
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.ORDERED.value, index=True)
    order_source_id: Mapped[str | None] = mapped_column(
        ForeignKey("order_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Product info (deprecated - kept for backward compatibility)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Customer info (CustomerAddressMixin provides: customer_name, customer_postal_code,
    # customer_address_prefecture, customer_address_city, customer_address_building, customer_phone)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Manufacturing data (deprecated - kept for backward compatibility)
    manufacturing_data_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturing_data_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    manufacturing_data_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Total price (sum of all items)
    total_price: Mapped[int] = mapped_column(Integer, default=0)

    # 配送予定日（MAX(items.expected_delivery_date) + 発送準備日数）
    estimated_shipping_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    # Timestamps
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relationships
    product: Mapped["Product | None"] = relationship()
    order_source: Mapped["OrderSource | None"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, order_number={self.order_number}, status={self.status})>"


class OrderItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Order item model - 受注明細."""

    __tablename__ = "order_items"

    order_id: Mapped[str] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )

    # 外部販売サイトのオリジナル商品ID (optional for backward compatibility)
    uid: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)

    # POD商品マスタへの紐づけ（product_typeから自動検索）
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))

    # 外部販売サイトの商品名
    product_name: Mapped[str] = mapped_column(String(200))

    # 製造種類（リクエストから直接設定）
    product_type: Mapped[str] = mapped_column(String(50), index=True)

    # 製品単位のステータス
    status: Mapped[str] = mapped_column(
        String(20), default=OrderItemStatus.ORDERED.value, index=True
    )

    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    design_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # メーカーからの納品予定日（注文作成時に営業日計算で算出、確定値）
    expected_delivery_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    # === 外部注文 v2（製造データ生成）用フィールド ===
    # 旧 v1 明細は全て NULL のまま → 旧挙動を完全維持（発注ゲートの対象外）。
    # rksyo の商品識別子（製造データキャッシュキー）
    product_code: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    # 製造データ生成の元データ（PNGレイヤーURL群）
    source_images: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    # 紐づく製造データ（キャッシュ本体）
    manufacturing_data_id: Mapped[str | None] = mapped_column(
        ForeignKey("manufacturing_data.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # 商品マスタへの参照
    # 製造データは OrderItem 読み込み時に常に selectin ロード（async lazy-load 回避）
    manufacturing_data: Mapped["ManufacturingData | None"] = relationship(lazy="selectin")

    @property
    def is_manufacturing_ready(self) -> bool:
        """メーカー発注（ORDERED→MANUFACTURING）が可能かどうか.

        製造データが不要な明細（v1 = manufacturing_data_id が NULL）は常に発注可。
        製造データが必要な明細は、紐づく行が ready の場合のみ発注可。
        """
        if self.manufacturing_data_id is None:
            return True
        md = self.manufacturing_data
        return md is not None and md.status == MfgDataStatus.READY.value

    @property
    def is_order_blocked(self) -> bool:
        """メーカー発注（→MANUFACTURING）できない明細か（is_order_blocked_status に委譲）."""
        return is_order_blocked_status(self.status, self.is_manufacturing_ready)

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, product_name={self.product_name}, quantity={self.quantity}, status={self.status})>"
