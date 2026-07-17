/**
 * Issue #79: 発注CSV・配送CSVの「商品種類」表示を発注リストの形式に統一
 *
 * 発注明細CSV（発注画面）の「商品タイプ」列を発注リストと同じ
 * `{商品種類} - {サイズ} - {位置} - {色}` 形式（半角 " - " 区切り、空要素スキップ）に
 * 統一する。商品タイプ名は発注リストに一致（acrylic_stand -> アクリルフィギュア）。
 */

import { describe, it, expect } from "vitest";
import {
  formatProductDetailForCsv,
  getCsvProductTypeName,
  CSV_PRODUCT_TYPE_LABELS,
} from "@/features/purchase-orders/utils/format-product-detail";

describe("formatProductDetailForCsv", () => {
  it("Tシャツ（サイズ/位置/色あり）を 'Tシャツ - L - 正面 - 白' に整形する", () => {
    expect(
      formatProductDetailForCsv({
        product_type: "tshirt",
        size: "L",
        position: "正面",
        color: "白",
      })
    ).toBe("Tシャツ - L - 正面 - 白");
  });

  it("空要素（position 無し）はスキップし余分な区切りを出さない", () => {
    expect(
      formatProductDetailForCsv({
        product_type: "sticker",
        size: "100x100mm",
        position: null,
        color: "ホワイト",
      })
    ).toBe("ステッカー - 100x100mm - ホワイト");
  });

  it("acrylic_stand は発注リストに一致する『アクリルフィギュア』で出力する", () => {
    const result = formatProductDetailForCsv({
      product_type: "acrylic_stand",
      size: "100mm",
      position: null,
      color: "クリア",
    });
    expect(result).toBe("アクリルフィギュア - 100mm - クリア");
  });

  it("サイズ/位置/色が全て null の場合は商品タイプ名のみを出力する", () => {
    expect(
      formatProductDetailForCsv({
        product_type: "tote_bag",
        size: null,
        position: null,
        color: null,
      })
    ).toBe("トートバッグ");
  });

  it("空文字列も値なし扱いでスキップする", () => {
    expect(
      formatProductDetailForCsv({
        product_type: "tshirt",
        size: "",
        position: "",
        color: "白",
      })
    ).toBe("Tシャツ - 白");
  });

  it("未知の商品タイプはコードをそのまま先頭に使う", () => {
    expect(
      formatProductDetailForCsv({
        product_type: "unknown_type",
        size: "S",
        position: null,
        color: null,
      })
    ).toBe("unknown_type - S");
  });
});

describe("getCsvProductTypeName / CSV_PRODUCT_TYPE_LABELS", () => {
  it("発注リスト（バックエンド PRODUCT_TYPE_NAMES）と同じ対応表を持つ", () => {
    expect(CSV_PRODUCT_TYPE_LABELS).toEqual({
      acrylic_keychain: "アクリルキーホルダー",
      acrylic_stand: "アクリルフィギュア",
      sticker: "ステッカー",
      tote_bag: "トートバッグ",
      mug: "マグカップ",
      tshirt: "Tシャツ",
    });
  });

  it("未知タイプはコードをそのまま返す", () => {
    expect(getCsvProductTypeName("something_new")).toBe("something_new");
  });
});
