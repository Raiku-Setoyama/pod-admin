"""Manufacturing data model - 製造データ生成キャッシュ.

外部注文(v2)で受け取った元データ(PNGレイヤー)から illustrator-vm で生成した
製造データ(.ai/.pdf)を、受注元×商品×サイズ×バリアント単位でキャッシュするテーブル。
同一キーの再注文では VM を再実行せず、保存済みファイルを再利用する。
"""

from enum import Enum

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MfgDataStatus(str, Enum):
    """製造データ生成ステータス."""

    PENDING = "pending"  # 生成待ち（未着手 / リトライ対象）
    GENERATING = "generating"  # 生成中（illustrator-vm 実行中）
    READY = "ready"  # 生成完了・ファイル保存済み
    FAILED = "failed"  # 生成失敗（error_message 参照）


class ManufacturingData(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """製造データ生成キャッシュ - 受注元×商品×サイズ×バリアント単位で1行."""

    __tablename__ = "manufacturing_data"

    # 受注元（サイト単位でキャッシュを名前空間分離）
    order_source_id: Mapped[str] = mapped_column(
        ForeignKey("order_sources.id", ondelete="CASCADE"), index=True
    )

    # rksyo の商品識別子（キャッシュキー）
    product_code: Mapped[str] = mapped_column(String(100), index=True)

    # pod-admin / VM の商品タイプ
    product_type: Mapped[str] = mapped_column(String(50))

    # pod-admin サイズ文字列（例: "50x50mm"）
    size: Mapped[str] = mapped_column(String(50))

    # VM互換バリアント（clear / color 等）。バリアントなし商品は NULL
    variant: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 生成ステータス
    status: Mapped[str] = mapped_column(String(20), default=MfgDataStatus.PENDING.value, index=True)

    # 生成に使用したレイヤーURL群 [{"layer_type": ..., "url": ...}]
    source_images: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)

    # illustrator-vm のジョブID（生成中の追跡用）
    vm_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # VM status 由来の出力ファイル名（二重拡張子回避のため status の値を正とする）
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FileStorage 保存先（ローカル相対パス or GCSオブジェクトキー）
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 直近の失敗理由
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # 生成試行回数
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        # キャッシュキー: 受注元×商品×サイズ×バリアント。
        # variant は NULL 可のため NULLS NOT DISTINCT (PostgreSQL 15+) で
        # 「バリアントなし」同士も一意に扱い、重複生成を防ぐ。
        Index(
            "uq_manufacturing_data_cache",
            "order_source_id",
            "product_code",
            "size",
            "variant",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ManufacturingData(id={self.id}, product_code={self.product_code}, "
            f"size={self.size}, variant={self.variant}, status={self.status})>"
        )
