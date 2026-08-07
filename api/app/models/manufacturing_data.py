"""Manufacturing data model.

外部注文（v2）の製造データキャッシュ本体。

illustrator-vm（Product Manufacturing API）で生成した製造データ（.ai/.pdf）を
「受注元 × 商品コード × サイズ × バリアント」単位で一度だけ生成し、pod-admin 側に
自前保存して再利用する。VM の生成結果は `(product_type, size, variant, 元画像)` の
純関数であり order_id には依存しないため、この単位でのキャッシュ再利用は妥当。
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MfgDataStatus(str, Enum):
    """製造データの生成ステータス."""

    PENDING = "pending"  # 生成待ち（行は作成済み、VM未起動）
    GENERATING = "generating"  # 生成中（VMジョブ実行中）
    READY = "ready"  # 生成完了（file_path に保存済み）
    FAILED = "failed"  # 生成失敗（error_message 参照）


class ManufacturingData(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """製造データキャッシュ（商品×サイズ×バリアント単位）."""

    __tablename__ = "manufacturing_data"
    __table_args__ = (
        # 受注元 × 商品コード × サイズ × バリアントで一意（キャッシュキー）。
        # サイズ/バリアントが NULL でも一意に扱うため NULLS NOT DISTINCT を使用（PG15+）。
        UniqueConstraint(
            "order_source_id",
            "product_code",
            "size",
            "variant",
            name="uq_manufacturing_data_cache_key",
            postgresql_nulls_not_distinct=True,
        ),
    )

    # 受注元（サイト単位で名前空間を分離）
    order_source_id: Mapped[str | None] = mapped_column(
        ForeignKey("order_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # rksyo の商品識別子（キャッシュキー）
    product_code: Mapped[str] = mapped_column(String(255), index=True)

    # pod-admin / VM の商品タイプ
    product_type: Mapped[str] = mapped_column(String(50))

    # pod-admin サイズ（元の受注値をそのまま保持）
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # VM バリアント（keychain: clear/color、sticker: clear、その他: None）
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 生成ステータス（MfgDataStatus の value を保存）
    status: Mapped[str] = mapped_column(
        String(20), default=MfgDataStatus.PENDING.value, index=True
    )

    # 使用したレイヤー群。外部受注由来は {"layer_type": "color", "url": "..."}、
    # 管理画面から差し替えたものは {"layer_type": "color", "file_path": "...", "filename": "..."}。
    source_images: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)

    # 元画像を管理画面から差し替えた最終時刻（未差し替えは NULL = 外部受注のまま）
    source_images_replaced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 差し替えた管理ユーザー（ユーザー削除後も履歴が残るようメールを保持）
    source_images_replaced_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # illustrator-vm のジョブID
    vm_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # VM status 由来の出力ファイル名
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FileStorage 上の保存先
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 失敗時のエラーメッセージ
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # 生成試行回数
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return (
            f"<ManufacturingData(id={self.id}, product_code={self.product_code}, "
            f"size={self.size}, variant={self.variant}, status={self.status})>"
        )
