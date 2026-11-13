"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type {
  ManufacturingDataStatus,
  MfgDataPrintRecord,
  ResolutionLevel,
  WhitePlateKind,
} from "@/types/api";

/**
 * DTF 版の製造データの「生成の結果の記録」（元画像の解像度・絵柄の大きさ・印刷位置・白版の種類）
 * を出す部品。一覧と詳細で使う。
 *
 * **区分の閾値は画面に持たない。** API が設定の閾値で判定した `resolution_level` をそのまま出す。
 */

const RESOLUTION_BADGES: Record<
  Exclude<ResolutionLevel, "ok">,
  { label: string; className: string; description: string }
> = {
  low: {
    label: "低解像度",
    className: "bg-orange-100 text-orange-800 border-orange-300",
    description:
      "元画像の解像度が特に低く、仕上がりが粗くなる場合があります。作成・発注はそのままできます（システムが拡大して作成しています）。",
  },
  upscaled: {
    label: "拡大して作成",
    className: "bg-slate-100 text-slate-700 border-slate-300",
    description:
      "元画像が目標の解像度に足りないため、システムが拡大して作成しました（細かさは元画像のまま）。",
  },
};

// **発注リスト（api/app/utils/order_list_generator.py の白版の列。#189）と同じ文言にする。**
// 発注の前に、発注リストに書く値をここで確かめるため
const WHITE_PLATE_LABELS: Record<WhitePlateKind, string> = {
  color_only: "カラーのみ（縮小なし）",
  white_only: "ホワイトのみ（縮小なし）",
  mixed: "混在（カラー部分を縮小済み）",
};

/**
 * 記録を出してよいか。**生成待ち・生成中・失敗の行は前回の値が残っている**
 * （再生成・元画像の差し替えでも次に ready になるまで上書きされない）ので、ready のときだけ出す。
 */
function isCurrent(status: ManufacturingDataStatus): boolean {
  return status === "ready";
}

/** 小数 1 桁まで（末尾の 0 は付けない）。 */
function formatNumber(value: number): string {
  return String(Number(value.toFixed(1)));
}

/**
 * dpi の表示。区分（149.9 は警告、150 は拡大）と食い違わないよう、**四捨五入せず切り捨てる**
 * （149.96 を「150 dpi・低解像度」と出さない）。
 */
/**
 * リブ下から絵柄の最上部まで（mm）を cm にする。**発注リストと同じく 0.1cm 単位に四捨五入**
 * （mm を整数に四捨五入してから 10 で割る。`(mm / 10).toFixed(1)` は 13.55 を 13.5 にしてしまう）。
 */
export function formatTopBelowRib(mm: number): string {
  return `${(Math.round(mm) / 10).toFixed(1)} cm`;
}

export function formatDpi(dpi: number): string {
  return `${String(Math.floor(dpi * 10) / 10)} dpi`;
}

export function ResolutionBadge({ level }: { level: ResolutionLevel | null }) {
  if (level === null || level === "ok") return null;
  const badge = RESOLUTION_BADGES[level];
  return (
    <Badge
      variant="outline"
      className={cn("border font-medium", badge.className)}
      title={badge.description}
    >
      {badge.label}
    </Badge>
  );
}

/** 一覧の「解像度」列。記録が無い（インクジェット版・アクリル系・過去のデータ）・生成中なら「—」。 */
export function ResolutionCell({
  record,
  status,
}: {
  record: MfgDataPrintRecord;
  status: ManufacturingDataStatus;
}) {
  if (!isCurrent(status) || record.source_dpi === null) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-1.5">
      <span className="whitespace-nowrap">{formatDpi(record.source_dpi)}</span>
      <ResolutionBadge level={record.resolution_level} />
    </span>
  );
}

/**
 * 詳細の「印刷の条件（DTF）」。発注リストに書く値を、発注の前にここで確かめられるようにする。
 */
export function PrintRecordDetails({
  record,
  status,
}: {
  record: MfgDataPrintRecord;
  status: ManufacturingDataStatus;
}) {
  if (!isCurrent(status)) {
    return <p className="text-sm text-muted-foreground">生成が終わると表示されます</p>;
  }

  const level = record.resolution_level;
  const badge = level === "low" || level === "upscaled" ? RESOLUTION_BADGES[level] : null;
  const size =
    record.art_width_mm !== null && record.art_height_mm !== null
      ? `${formatNumber(record.art_width_mm)} × ${formatNumber(record.art_height_mm)} mm`
      : "—";
  const top =
    record.art_top_below_rib_mm !== null ? formatTopBelowRib(record.art_top_below_rib_mm) : "—";

  return (
    <div className="space-y-2">
      <dl className="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-muted-foreground">元画像の解像度</dt>
        <dd className="flex flex-wrap items-center gap-1.5">
          {record.source_dpi !== null ? formatDpi(record.source_dpi) : "—"}
          <ResolutionBadge level={level} />
        </dd>
        <dt className="text-muted-foreground">絵柄の大きさ</dt>
        <dd>{size}</dd>
        <dt className="text-muted-foreground">リブ下から絵柄の最上部まで</dt>
        <dd>{top}</dd>
        <dt className="text-muted-foreground">白版の種類</dt>
        <dd>{record.white_plate ? WHITE_PLATE_LABELS[record.white_plate] : "—"}</dd>
      </dl>
      {badge && (
        <p
          className={cn(
            "rounded-md border p-3 text-xs",
            level === "low"
              ? "border-orange-200 bg-orange-50 text-orange-900"
              : "border-slate-200 bg-slate-50 text-slate-700",
          )}
        >
          {badge.description}
        </p>
      )}
    </div>
  );
}
