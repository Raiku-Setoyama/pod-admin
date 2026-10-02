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
import {
  MANUFACTURING_DATA_STATUS_COLORS,
  MANUFACTURING_DATA_STATUS_LABELS,
} from "@/constants/status";
import { getProductTypeLabel } from "@/constants/product";
import { cn, formatDateTime } from "@/lib/utils";
import type { ManufacturingDataRow } from "@/types/api";

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
  /** 選択中の ID。`onSelectChange` を渡したときだけ選択列が出る。 */
  selectedIds?: string[];
  onSelectChange?: (ids: string[]) => void;
}

export function ManufacturingDataList({
  items,
  selectedIds = [],
  onSelectChange,
}: ManufacturingDataListProps) {
  const hasSelection = onSelectChange !== undefined;
  // **選べるのは失敗した行だけである。** ready を巻き戻すと、その行を共有する
  // 他の注文の発注可否まで落ちる（API 側も failed 以外は受け付けない）。
  const selectableIds = items.filter((i) => i.status === "failed").map((i) => i.id);
  const selectedCount = selectedIds.filter((id) => selectableIds.includes(id)).length;
  const allSelected = selectableIds.length > 0 && selectedCount === selectableIds.length;
  const someSelected = selectedCount > 0 && !allSelected;

  const handleSelectAll = (checked: boolean) => {
    onSelectChange?.(checked ? selectableIds : []);
  };

  const handleSelectOne = (id: string, checked: boolean) => {
    onSelectChange?.(
      checked ? [...selectedIds, id] : selectedIds.filter((x) => x !== id),
    );
  };

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
            {hasSelection && (
              <TableHead className="w-12">
                {selectableIds.length > 0 && (
                  <Checkbox
                    checked={someSelected ? "indeterminate" : allSelected}
                    onCheckedChange={handleSelectAll}
                    aria-label="失敗した行をすべて選択"
                  />
                )}
              </TableHead>
            )}
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
                {hasSelection && (
                  <TableCell>
                    {row.status === "failed" && (
                      <Checkbox
                        checked={selectedIds.includes(row.id)}
                        onCheckedChange={(checked) =>
                          handleSelectOne(row.id, checked === true)
                        }
                        aria-label={`${row.product_code} を選択`}
                      />
                    )}
                  </TableCell>
                )}
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      "border font-medium",
                      MANUFACTURING_DATA_STATUS_COLORS[row.status],
                    )}
                  >
                    {MANUFACTURING_DATA_STATUS_LABELS[row.status] ?? row.status}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">{row.product_code}</TableCell>
                <TableCell>{getProductTypeLabel(row.product_type)}</TableCell>
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
