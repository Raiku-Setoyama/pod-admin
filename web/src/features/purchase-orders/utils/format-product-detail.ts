/**
 * 発注明細CSV用の「商品種類」列フォーマッタ。
 *
 * 発注リスト（バックエンド order_list_generator）と同じ
 * `{商品種類} - {サイズ} - {位置} - {色}` 形式（半角 " - " 区切り、
 * 値が無い要素はスキップ）で組み立てる。
 *
 * 商品タイプ名はバックエンドの PRODUCT_TYPE_NAMES に一致させる
 * （特に acrylic_stand -> アクリルフィギュア）。画面表示ラベルとは
 * 別物なので注意（画面側は「アクリルスタンド」表記を維持する）。
 */

// バックエンド app/utils/order_list_generator.py の PRODUCT_TYPE_NAMES と一致させる
export const CSV_PRODUCT_TYPE_LABELS: Record<string, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルフィギュア",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  mug: "マグカップ",
  tshirt: "Tシャツ",
};

/** 商品タイプコードから発注リスト準拠の日本語名を得る。 */
export function getCsvProductTypeName(productType: string): string {
  return CSV_PRODUCT_TYPE_LABELS[productType] ?? productType;
}

export interface ProductDetailParts {
  product_type: string;
  size: string | null;
  position: string | null;
  color: string | null;
}

/**
 * 「商品種類」列の文字列を組み立てる: {商品種類} - {サイズ} - {位置} - {色}。
 * size / position / color が null/空 の要素はスキップし、余分な区切りを出さない。
 *
 * @example
 *   formatProductDetailForCsv({ product_type: "tshirt", size: "L", position: "正面", color: "白" })
 *   // => "Tシャツ - L - 正面 - 白"
 *   formatProductDetailForCsv({ product_type: "sticker", size: "100x100mm", position: null, color: "ホワイト" })
 *   // => "ステッカー - 100x100mm - ホワイト"
 */
export function formatProductDetailForCsv(item: ProductDetailParts): string {
  const parts = [getCsvProductTypeName(item.product_type)];
  if (item.size) parts.push(item.size);
  if (item.position) parts.push(item.position);
  if (item.color) parts.push(item.color);
  return parts.join(" - ");
}
