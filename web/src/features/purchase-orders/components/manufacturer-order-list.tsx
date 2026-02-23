"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { StatusBadge } from "@/components/common/status-badge";
import type { ManufacturerOrderSummary } from "@/types/api";

interface ManufacturerOrderListProps {
  manufacturers: ManufacturerOrderSummary[];
  onRowClick?: (manufacturer: ManufacturerOrderSummary) => void;
}

function formatPrice(price: number): string {
  return `¥${price.toLocaleString()}`;
}

export function ManufacturerOrderList({
  manufacturers,
  onRowClick,
}: ManufacturerOrderListProps) {
  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>メーカー名</TableHead>
            <TableHead className="text-center">発注中明細数</TableHead>
            <TableHead className="text-center">合計数量</TableHead>
            <TableHead className="text-right">合計金額</TableHead>
            <TableHead className="text-center">リードタイム</TableHead>
            <TableHead>ステータス</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {manufacturers.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={6}
                className="h-24 text-center text-muted-foreground"
              >
                発注中の明細がありません
              </TableCell>
            </TableRow>
          ) : (
            manufacturers.map((m) => (
              <TableRow
                key={m.id}
                className="cursor-pointer hover:bg-accent/50"
                onClick={() => onRowClick?.(m)}
              >
                <TableCell className="font-medium">{m.name}</TableCell>
                <TableCell className="text-center">
                  {m.ordered_item_count}件
                </TableCell>
                <TableCell className="text-center">
                  {m.total_quantity}点
                </TableCell>
                <TableCell className="text-right">
                  {formatPrice(m.total_amount)}
                </TableCell>
                <TableCell className="text-center">
                  {m.lead_time_days}日
                </TableCell>
                <TableCell>
                  <StatusBadge status={m.status ?? "ordered"} />
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
