"""Product attribute models."""

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProductAttributeOption(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """有効な属性値（size/color/position）を管理するテーブル."""

    __tablename__ = "product_attribute_options"
    __table_args__ = (
        UniqueConstraint(
            "product_type", "attribute_name", "attribute_value",
            name="uq_product_attr_type_name_value",
        ),
    )

    product_type: Mapped[str] = mapped_column(String(50), index=True)
    attribute_name: Mapped[str] = mapped_column(String(20))  # "size", "color", "position"
    attribute_value: Mapped[str] = mapped_column(String(50))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return (
            f"<ProductAttributeOption("
            f"{self.product_type}/{self.attribute_name}={self.attribute_value})>"
        )


class ProductAttributeRequirement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """商品種別ごとの属性必須設定."""

    __tablename__ = "product_attribute_requirements"
    __table_args__ = (
        UniqueConstraint("product_type", name="uq_product_attr_req_type"),
    )

    product_type: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    required_size: Mapped[bool] = mapped_column(Boolean, default=True)
    required_color: Mapped[bool] = mapped_column(Boolean, default=False)
    required_position: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return f"<ProductAttributeRequirement({self.product_type})>"
