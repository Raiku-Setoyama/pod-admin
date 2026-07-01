"""pod-admin の商品属性を illustrator-vm（Product Manufacturing API）の属性へ変換する.

illustrator-vm は `config/products.yaml` を正として以下を要求する:

- tshirt:           single / S,M,L,XL          / variant なし / PDF
- tote_bag:         single / M                 / variant なし / PDF
- acrylic_keychain: multi(color+cutline[+white]) / variant 必須(clear/color) / 50x50,70x70,100x100 / AI
- acrylic_stand:    multi(color+cutline[+white]) / variant なし              / 50mm,70mm,100mm      / AI
- sticker:          multi(color+cutline)         / variant 必須(clear)       / 50x50,70x70,100x100  / AI

注: mug_cup は VM 側では対応しているが pod-admin の ProductType に未定義のため本スコープ外。

バリアントは受注値ではなく「提供された元データのレイヤー構成」から決定的に導出する:
- keychain: white レイヤーがあれば "color"（白版あり）、なければ "clear"
- sticker:  常に "clear"（white は扱わない）
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

# レイヤー種別
LAYER_COLOR = "color"
LAYER_CUTLINE = "cutline"
LAYER_WHITE = "white"
LAYER_DESIGN = "design"

# 入力モード
INPUT_MODE_SINGLE = "single"
INPUT_MODE_MULTI = "multi"


class MfgMappingError(ValueError):
    """商品属性を VM 属性へ変換できない場合のエラー."""


@dataclass(frozen=True)
class VmMapping:
    """illustrator-vm へ渡す製造データ生成パラメータ."""

    product_type: str
    size: str
    variant: str | None
    input_mode: str
    # 送信必須のレイヤー種別
    required_layers: tuple[str, ...]
    # 提供されていれば送信する任意レイヤー種別
    optional_layers: tuple[str, ...] = field(default_factory=tuple)
    # 生成物の拡張子（保存/命名のフォールバック。実ファイル名は VM の output_filename を正とする）
    output_ext: str = ".ai"

    @property
    def usable_layers(self) -> tuple[str, ...]:
        """required + optional の全レイヤー種別."""
        return self.required_layers + self.optional_layers


# サイズ正規化テーブル（product_type -> {pod-admin size: VM size}）
_SIZE_MAPS: dict[str, dict[str, str]] = {
    "acrylic_keychain": {"50x50mm": "50x50", "70x70mm": "70x70", "100x100mm": "100x100"},
    "sticker": {"50x50mm": "50x50", "70x70mm": "70x70", "100x100mm": "100x100"},
    "acrylic_stand": {"50x50mm": "50mm", "70x70mm": "70mm", "100x100mm": "100mm"},
    "tshirt": {"S": "S", "M": "M", "L": "L", "XL": "XL"},
    "tote_bag": {"M": "M"},
}


def _normalize_size(product_type: str, size: str | None) -> str:
    """pod-admin のサイズを VM サイズへ正規化する."""
    if not size:
        raise MfgMappingError(f"size is required for product_type '{product_type}'")
    size_map = _SIZE_MAPS[product_type]
    normalized = size_map.get(size)
    if normalized is None:
        raise MfgMappingError(
            f"Unsupported size '{size}' for product_type '{product_type}'. "
            f"Valid: {sorted(size_map)}"
        )
    return normalized


def build_vm_mapping(
    product_type: str,
    size: str | None,
    provided_layers: Iterable[str],
) -> VmMapping:
    """pod-admin の商品属性から VM 生成パラメータを構築する.

    Args:
        product_type: pod-admin の商品タイプ（tshirt / acrylic_keychain 等）。
        size: pod-admin のサイズ（例 "50x50mm", "M"）。
        provided_layers: v2 明細の source_images で提供されたレイヤー種別の集合。

    Raises:
        MfgMappingError: 未対応の商品タイプ／サイズ、または必須レイヤー不足の場合。
    """
    layers = set(provided_layers)

    if product_type in ("tshirt", "tote_bag"):
        # 単一画像商品: design（無ければ color）1枚
        if LAYER_DESIGN in layers:
            required = (LAYER_DESIGN,)
        elif LAYER_COLOR in layers:
            required = (LAYER_COLOR,)
        else:
            raise MfgMappingError(
                f"product_type '{product_type}' requires a 'design' (or 'color') layer"
            )
        return VmMapping(
            product_type=product_type,
            size=_normalize_size(product_type, size),
            variant=None,
            input_mode=INPUT_MODE_SINGLE,
            required_layers=required,
            output_ext=".pdf",
        )

    if product_type == "acrylic_keychain":
        _require_layers(product_type, layers, (LAYER_COLOR, LAYER_CUTLINE))
        variant = "color" if LAYER_WHITE in layers else "clear"
        return VmMapping(
            product_type=product_type,
            size=_normalize_size(product_type, size),
            variant=variant,
            input_mode=INPUT_MODE_MULTI,
            required_layers=(LAYER_COLOR, LAYER_CUTLINE),
            optional_layers=(LAYER_WHITE,),
            output_ext=".ai",
        )

    if product_type == "acrylic_stand":
        _require_layers(product_type, layers, (LAYER_COLOR, LAYER_CUTLINE))
        return VmMapping(
            product_type=product_type,
            size=_normalize_size(product_type, size),
            variant=None,
            input_mode=INPUT_MODE_MULTI,
            required_layers=(LAYER_COLOR, LAYER_CUTLINE),
            optional_layers=(LAYER_WHITE,),
            output_ext=".ai",
        )

    if product_type == "sticker":
        _require_layers(product_type, layers, (LAYER_COLOR, LAYER_CUTLINE))
        # sticker は variants(clear) が定義された商品 = variant 必須（省略不可）
        return VmMapping(
            product_type=product_type,
            size=_normalize_size(product_type, size),
            variant="clear",
            input_mode=INPUT_MODE_MULTI,
            required_layers=(LAYER_COLOR, LAYER_CUTLINE),
            output_ext=".ai",
        )

    raise MfgMappingError(f"Unsupported product_type '{product_type}' for manufacturing data")


def _require_layers(product_type: str, layers: set[str], required: tuple[str, ...]) -> None:
    missing = [layer for layer in required if layer not in layers]
    if missing:
        raise MfgMappingError(
            f"product_type '{product_type}' requires layers {list(required)}; "
            f"missing: {missing}"
        )
