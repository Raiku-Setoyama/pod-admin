"""Manufacturing data model.

外部注文（v2）の製造データキャッシュ本体。

製造データ（.ai/.pdf）を「受注元 × 商品コード × サイズ × バリアント」単位で一度だけ
生成し、保存して再利用する。生成結果は `(product_type, size, variant, 元画像)` の
純関数であり order_id には依存しないため、この単位でのキャッシュ再利用は妥当。
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MfgDataStatus(str, Enum):
    """製造データの生成ステータス."""

    PENDING = "pending"  # 生成待ち（行は作成済み、まだ生成していない）
    GENERATING = "generating"  # 生成中（ワーカーが確保している）
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

    # pod-admin の商品タイプ
    product_type: Mapped[str] = mapped_column(String(50))

    # pod-admin サイズ（元の受注値をそのまま保持）
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 生成のバリアント（keychain: clear/color、sticker: clear、T シャツ・トートの DTF 版: dtf、
    # その他: None）。**生成はこの値で作り方を決める**（設定の切り替えで、既にある行の作り方を変えない）
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

    # 以前の製造データ生成 VM（illustrator-vm）のジョブID。REQ-0067 からは書かない。
    # 過去の行の記録として残している（列の削除はマイグレーションを伴うので、REQ-0068 のスコープ外）
    vm_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 出力ファイル名（製造委託先に渡すときの名前）
    output_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FileStorage 上の保存先
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 生成の結果の記録（T シャツ・トートの DTF 版だけ。インクジェット版・アクリル系は NULL。#188）。
    # 生成が ready になったときに書く。発注リスト（#189）と管理画面（#190）が使う。
    # 元画像の実寸解像度（dpi。元の画素数 ÷ 置く大きさ）
    source_dpi: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 絵柄の幅・高さ（mm。切り抜く前の絵柄の外形）
    art_width_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    art_height_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # リブ下から絵柄の最上部まで（mm）
    art_top_below_rib_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 白版の種類（color_only / white_only / mixed＝カラーのみ／ホワイトのみ／混在。
    # 値は生成 app/generator/dtf.py の WhitePlateKind）
    white_plate: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 失敗時のエラーメッセージ
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # 生成試行回数
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # 生成の所有権（リース）の期限。generating へ確保するときに打ち、ready/failed で NULL に戻す。
    #
    # **これが「その行を今まさに誰かが処理しているか」の唯一の根拠である。**
    # 期限を過ぎた generating は、処理していたワーカーが落ちたものと見なして pending へ戻す。
    # ワーカーが何本走っているかに依存しないので、復旧処理は単独で正しく動く。
    #
    # 期限は 1 件の生成にかかりうる最大時間より十分に長くすること。短すぎると、生きている
    # ワーカーが処理中の行を別のワーカーが奪い、生成が二重に走る。
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ManufacturingData(id={self.id}, product_code={self.product_code}, "
            f"size={self.size}, variant={self.variant}, status={self.status})>"
        )
