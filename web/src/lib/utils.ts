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
