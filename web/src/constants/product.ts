import type { ProductType } from "@/types/api";

/**
 * 商品種別の画面表示名。
 *
 * **同じ表を画面ごとに書き写さない。** 商品種別が増えるたびに探し回ることになり、
 * 書き漏らした画面だけが英語のキーを出す。
 *
 * CSV・帳票の表記はここではなく
 * `features/purchase-orders/utils/format-product-detail.ts` が持つ。
 * **意図的に別である**（帳票はアクリルスタンドを「アクリルフィギュア」と書く）。
 */
export const PRODUCT_TYPE_LABELS: Record<ProductType, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  tshirt: "Tシャツ",
};

/** 商品種別の表示名を返す（未知の値はキーをそのまま出す）。 */
export function getProductTypeLabel(productType: ProductType | string): string {
  return PRODUCT_TYPE_LABELS[productType as ProductType] ?? productType;
}
