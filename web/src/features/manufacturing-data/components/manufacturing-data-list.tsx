"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import type { ManufacturingDataRow, ManufacturingDataStatus, ProductType } from "@/types/api";

const productTypeLabels: Record<ProductType, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  tshirt: "Tシャツ",
};

const statusLabels: Record<ManufacturingDataStatus, string> = {
  pending: "生成待ち",
  generating: "生成中",
  ready: "完成",
  failed: "生成失敗",
};

const statusVariants: Record<
  ManufacturingDataStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  pending: "outline",
  generating: "secondary",
  ready: "default",
  failed: "destructive",
};

function formatDateTime(value: string | null): string {
  return value ? new Date(value).toLocaleString("ja-JP") : "—";
}

/**
 * 「生成待ち」の内訳を出す。
 *
 * **pending は 2 つの意味を持つ。** 一度も試していない行と、VM に届かなくて
 * 待たされている行である。後者を「生成待ち」とだけ表示すると、VM が落ちていることが
 * 画面から読み取れない。区別は保存しておらず、再試行の予定時刻から導く。
 */
function pendingDetail(row: ManufacturingDataRow): string | null {
  if (row.status !== "pending" || !row.next_attempt_at) return null;
  return `VM に届かず待機中（${row.attempts} 回目・${formatDateTime(row.next_attempt_at)} 以降に再試行）`;
}

interface ManufacturingDataListProps {
  items: ManufacturingDataRow[];
  selectedIds: string[];
  onToggle: (id: string) => void;
  onToggleAll: () => void;
  /** 選択できる行（= failed）があるか。無ければ全選択のチェックボックスを出さない。 */
  selectableIds: string[];
}

export function ManufacturingDataList({
  items,
  selectedIds,
  onToggle,
  onToggleAll,
  selectableIds,
}: ManufacturingDataListProps) {
  const allSelected =
    selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));

  if (items.length === 0) {
    return (
      <div className="rounded-md border border-border bg-white p-8 text-center text-sm text-muted-foreground">
        該当する製造データはありません
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              {selectableIds.length > 0 && (
                <Checkbox
                  checked={allSelected}
                  onCheckedChange={onToggleAll}
                  aria-label="失敗した行をすべて選択"
                />
              )}
            </TableHead>
            <TableHead>ステータス</TableHead>
            <TableHead>商品コード</TableHead>
            <TableHead>商品種別</TableHead>
            <TableHead>サイズ / バリアント</TableHead>
            <TableHead>試行</TableHead>
            <TableHead>更新</TableHead>
            <TableHead>詳細</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((row) => {
            const detail = pendingDetail(row);
            return (
              <TableRow key={row.id}>
                <TableCell>
                  {row.status === "failed" && (
                    <Checkbox
                      checked={selectedIds.includes(row.id)}
                      onCheckedChange={() => onToggle(row.id)}
                      aria-label={`${row.product_code} を選択`}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariants[row.status]}>
                    {statusLabels[row.status]}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{row.product_code}</TableCell>
                <TableCell>{productTypeLabels[row.product_type] ?? row.product_type}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {[row.size, row.variant].filter(Boolean).join(" / ") || "—"}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {row.attempts}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatDateTime(row.updated_at)}
                </TableCell>
                <TableCell className="max-w-md text-xs text-muted-foreground">
                  {detail ?? row.error_message ?? row.output_filename ?? "—"}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
