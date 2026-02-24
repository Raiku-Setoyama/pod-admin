"""Order model."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CustomerAddressMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.order_source import OrderSource
    from app.models.order_status_history import OrderStatusHistory
    from app.models.product import Product


class OrderStatus(str, Enum):
    """Order status."""

    ORDERED = "ordered"  # 発注済み（初期ステータス）
    MANUFACTURING = "manufacturing"  # 製造中
    DELIVERED = "delivered"  # 納入済み
    SHIPPED = "shipped"  # 発送完了（最終ステータス）


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

    # Timestamps
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relationships
    product: Mapped["Product | None"] = relationship()
    order_source: Mapped["OrderSource | None"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    status_history: Mapped[list["OrderStatusHistory"]] = relationship(
        cascade="all, delete-orphan"
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

    price: Mapped[int] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    design_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()  # 商品マスタへの参照

    def __repr__(self) -> str:
        return f"<OrderItem(id={self.id}, product_name={self.product_name}, quantity={self.quantity})>"
