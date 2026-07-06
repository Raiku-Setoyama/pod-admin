"""Product attribute mapping for illustrator-vm manufacturing data generation.

pod-admin の (product_type, size, variant) を illustrator-vm が要求する
(size id, variant, input_mode, required layers) へ決定的に変換する純粋ロジック。
対象は5タイプ（tshirt / tote_bag / acrylic_keychain / acrylic_stand / sticker）。
mug_cup は本Issueのスコープ外。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.utils.exceptions import ValidationError

# レイヤー種別
LAYER_COLOR = "color"
LAYER_CUTLINE = "cutline"
LAYER_WHITE = "white"
LAYER_DESIGN = "design"

# 単一画像商品で「デザイン」として扱えるレイヤー種別（design を正、color を別名として許容）
_SINGLE_IMAGE_LAYERS = (LAYER_DESIGN, LAYER_COLOR)


@dataclass(frozen=True)
class _ProductMfgConfig:
    """商品タイプごとの製造データ生成設定."""

    input_mode: str  # "single" | "multi"
    sizes: dict[str, str]  # pod-admin size -> VM size id
    required_layers: tuple[str, ...]
    optional_layers: tuple[str, ...]
    allowed_variants: frozenset[str] | None  # None => バリアントなし商品
    output_format: str  # "ai" | "pdf"


_PRODUCT_MFG_CONFIG: dict[str, _ProductMfgConfig] = {
    "tshirt": _ProductMfgConfig(
        input_mode="single",
        sizes={"S": "S", "M": "M", "L": "L", "XL": "XL"},
        required_layers=(LAYER_DESIGN,),
        optional_layers=(),
        allowed_variants=None,
        output_format="pdf",
    ),
    "tote_bag": _ProductMfgConfig(
        input_mode="single",
        sizes={"M": "M"},
        required_layers=(LAYER_DESIGN,),
        optional_layers=(),
        allowed_variants=None,
        output_format="pdf",
    ),
    "acrylic_keychain": _ProductMfgConfig(
        input_mode="multi",
        sizes={"50x50mm": "50x50", "70x70mm": "70x70", "100x100mm": "100x100"},
        required_layers=(LAYER_COLOR, LAYER_CUTLINE),
        optional_layers=(LAYER_WHITE,),
        allowed_variants=frozenset({"clear", "color"}),
        output_format="ai",
    ),
    "acrylic_stand": _ProductMfgConfig(
        input_mode="multi",
        sizes={"50x50mm": "50mm", "70x70mm": "70mm", "100x100mm": "100mm"},
        required_layers=(LAYER_COLOR, LAYER_CUTLINE),
        optional_layers=(LAYER_WHITE,),
        allowed_variants=None,
        output_format="ai",
    ),
    "sticker": _ProductMfgConfig(
        input_mode="multi",
        sizes={"50x50mm": "50x50", "70x70mm": "70x70", "100x100mm": "100x100"},
        required_layers=(LAYER_COLOR, LAYER_CUTLINE),
        optional_layers=(),
        allowed_variants=frozenset({"clear"}),
        output_format="ai",
    ),
}

SUPPORTED_PRODUCT_TYPES = frozenset(_PRODUCT_MFG_CONFIG)


@dataclass(frozen=True)
class VmMapping:
    """illustrator-vm へ渡す製造データ生成パラメータ."""

    product_type: str
    vm_size: str
    variant: str | None
    input_mode: str
    required_layers: tuple[str, ...]
    optional_layers: tuple[str, ...]
    output_format: str


def _get_config(product_type: str) -> _ProductMfgConfig:
    config = _PRODUCT_MFG_CONFIG.get(product_type)
    if config is None:
        supported = ", ".join(sorted(_PRODUCT_MFG_CONFIG))
        raise ValidationError(
            f"product_type '{product_type}' は製造データ生成の対象外です（対象: {supported}）。"
        )
    return config


def is_supported(product_type: str) -> bool:
    """製造データ生成の対象商品タイプかどうか."""
    return product_type in _PRODUCT_MFG_CONFIG


def normalize_variant(product_type: str, variant: str | None) -> str | None:
    """キャッシュキー / VM 用に variant を正規化・検証する.

    - バリアント必須商品（keychain / sticker）: 許可値でなければ ValidationError。
    - バリアントなし商品（tshirt / tote_bag / acrylic_stand）: 常に None（送られても無視）。
    """
    config = _get_config(product_type)
    if config.allowed_variants is None:
        return None
    normalized = (variant or "").strip()
    if normalized not in config.allowed_variants:
        allowed = ", ".join(sorted(config.allowed_variants))
        raise ValidationError(
            f"product_type '{product_type}' には variant が必須です"
            f"（許可値: {allowed}）。受信値: {variant!r}"
        )
    return normalized


def resolve_vm_mapping(product_type: str, size: str | None, variant: str | None) -> VmMapping:
    """(product_type, size, variant) を VM パラメータへ変換する。不正な組合せは ValidationError。"""
    config = _get_config(product_type)

    size_key = (size or "").strip()
    vm_size = config.sizes.get(size_key)
    if vm_size is None:
        allowed = ", ".join(config.sizes)
        raise ValidationError(
            f"product_type '{product_type}' の size '{size}' は未対応です（許可値: {allowed}）。"
        )

    normalized_variant = normalize_variant(product_type, variant)

    return VmMapping(
        product_type=product_type,
        vm_size=vm_size,
        variant=normalized_variant,
        input_mode=config.input_mode,
        required_layers=config.required_layers,
        optional_layers=config.optional_layers,
        output_format=config.output_format,
    )


def select_layers(product_type: str, source_images: list[dict[str, str]] | None) -> dict[str, str]:
    """source_images から VM に渡す「レイヤー種別 -> URL」辞書を組み立て・検証する。

    - single 商品: design（無ければ color を別名として使用）1枚を {"design": url} で返す。
    - multi 商品: required 全て（＋あれば optional）を {layer_type: url} で返す。
    不足・未対応レイヤーがあれば ValidationError。
    """
    config = _get_config(product_type)
    images = source_images or []

    by_type: dict[str, str] = {}
    for entry in images:
        layer_type = (entry.get("layer_type") or "").strip()
        url = (entry.get("url") or "").strip()
        if layer_type and url:
            by_type[layer_type] = url

    if config.input_mode == "single":
        for candidate in _SINGLE_IMAGE_LAYERS:
            if candidate in by_type:
                return {LAYER_DESIGN: by_type[candidate]}
        raise ValidationError(
            f"product_type '{product_type}' には元画像"
            f"（{' または '.join(_SINGLE_IMAGE_LAYERS)}）が1枚必要です。"
        )

    valid_layers = set(config.required_layers) | set(config.optional_layers)
    unknown = set(by_type) - valid_layers
    if unknown:
        raise ValidationError(
            f"product_type '{product_type}' に未対応のレイヤーが含まれています: "
            f"{', '.join(sorted(unknown))}"
        )
    missing = [layer for layer in config.required_layers if layer not in by_type]
    if missing:
        raise ValidationError(
            f"product_type '{product_type}' に必要なレイヤーが不足しています: {', '.join(missing)}"
        )

    selected = {layer: by_type[layer] for layer in config.required_layers}
    for layer in config.optional_layers:
        if layer in by_type:
            selected[layer] = by_type[layer]
    return selected


def validate_v2_item(
    product_type: str,
    size: str | None,
    variant: str | None,
    source_images: list[dict[str, str]] | None,
) -> VmMapping:
    """v2 明細の製造データ生成可能性を検証し、VM マッピングを返す（intake で使用）。

    product_type / size / variant / 必須レイヤーのいずれかが不正なら ValidationError。
    """
    mapping = resolve_vm_mapping(product_type, size, variant)
    select_layers(product_type, source_images)  # レイヤー検証（不正時に例外送出）
    return mapping
