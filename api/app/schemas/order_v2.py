"""v2 order intake schemas.

外部販売サイト(v2)からの注文受付用スキーマ。完成データURLではなく、製造データ生成の
元データ(PNGレイヤーの source_images) と product_code / variant を受け取る。
"""

from pydantic import BaseModel, Field

from app.models.product import ProductType
from app.schemas.order import CustomerInfo


class SourceImage(BaseModel):
    """製造データ生成の元データ（レイヤー種別ごとのPNG URL）."""

    layer_type: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="レイヤー種別 (color / cutline / white / design)",
    )
    url: str = Field(..., min_length=1, max_length=2048)


class OrderItemCreateV2(BaseModel):
    """v2 受注明細（製造データ生成の元データ付き）."""

    uid: str = Field(
        ...,
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
        description="製品番号（7桁数字）",
        examples=["0000001"],
    )
    product_type: ProductType
    product_name: str = Field(..., min_length=1, max_length=200)
    price: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    size: str | None = Field(None, max_length=50)

    # 製造データ生成用（新規）
    product_code: str = Field(
        ..., min_length=1, max_length=100, description="rksyo の商品識別子（キャッシュキー）"
    )
    variant: str | None = Field(
        None, max_length=50, description="VM互換バリアント（keychain: clear/color, sticker: clear）"
    )
    source_images: list[SourceImage] = Field(
        ..., min_length=1, description="元データPNGレイヤーのURL群"
    )

    thumbnail_image_url: str | None = Field(None, max_length=2048)


class OrderCreateV2(BaseModel):
    """v2 受注作成スキーマ."""

    order_number: str = Field(
        ...,
        min_length=7,
        max_length=7,
        pattern=r"^\d{7}$",
        description="受注番号（7桁数字）",
        examples=["0000001"],
    )
    customer: CustomerInfo
    items: list[OrderItemCreateV2] = Field(..., min_length=1)
