"""Product model."""

from enum import Enum

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProductType(str, Enum):
    """Product types."""

    ACRYLIC_KEYCHAIN = "acrylic_keychain"  # アクリルキーホルダー
    ACRYLIC_STAND = "acrylic_stand"  # アクリルスタンド
    STICKER = "sticker"  # ステッカー
    TOTE_BAG = "tote_bag"  # トートバッグ
    TSHIRT = "tshirt"  # Tシャツ


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Product model for product master."""

    __tablename__ = "products"
    # Unique index: uq_products_type_size_position_color
    # Partial unique index on (product_type, size, position, color) for active products.
    # Created via Alembic migration (add_product_uq_001) with NULLS NOT DISTINCT.
    # Application-level duplicate check is enforced in ProductService.

    product_type: Mapped[str] = mapped_column(String(50), index=True)
    size: Mapped[str] = mapped_column(String(50))
    position: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturer_id: Mapped[str] = mapped_column(ForeignKey("manufacturers.id"))
    cost: Mapped[int] = mapped_column(Integer)
    lead_time_days: Mapped[int] = mapped_column(Integer)
    order_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="products")

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, type={self.product_type}, size={self.size})>"


# Import here to avoid circular imports
from app.models.manufacturer import Manufacturer  # noqa: E402, F401
