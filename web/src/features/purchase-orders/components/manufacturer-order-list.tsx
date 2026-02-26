"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ManufacturerOrderSummary } from "@/types/api";

interface ManufacturerOrderListProps {
  manufacturers: ManufacturerOrderSummary[];
  onRowClick?: (manufacturer: ManufacturerOrderSummary) => void;
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
            <TableHead className="text-center">リードタイム</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {manufacturers.length === 0 ? (
            <TableRow>
              <TableCell
                colSpan={4}
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
                <TableCell className="text-center">
                  {m.lead_time_days}日
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
