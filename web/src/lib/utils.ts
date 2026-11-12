import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * 日時の表示用フォーマッタ。
 *
 * **モジュールの読み込み時に 1 つだけ作る。** `toLocaleString` は呼ぶたびに
 * フォーマッタを組み立てるので、20 行の表では 1 描画あたり数十回の構築になる
 * （この一覧は定期的に取り直すため、その分だけ繰り返される）。
 */
const dateTimeFormatter = new Intl.DateTimeFormat("ja-JP", {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

/** ISO 文字列を日本語表記の日時にする。未設定は em dash を返す。 */
export function formatDateTime(value: string | null | undefined): string {
  return value ? dateTimeFormatter.format(new Date(value)) : "—";
}

/**
 * 外部 URL をリンクにしてよいか判定し、よければその URL を返す。
 *
 * **外部受注由来の URL は、販売サイトが API で送ってきた値である。** `javascript:` などを
 * `href` に入れると、クリックした管理者の画面（管理画面のオリジン）でスクリプトが動く
 * （アクセストークンは localStorage にある）。scheme が http / https のときだけ返し、
 * それ以外（パースできない値も含む）は null を返す。
 */
export function safeExternalUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const { protocol } = new URL(url);
    return protocol === "https:" || protocol === "http:" ? url : null;
  } catch {
    return null;
  }
}
