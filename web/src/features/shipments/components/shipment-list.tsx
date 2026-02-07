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
import type { Shipment } from "@/types/api";

interface ShipmentListProps {
  shipments: Shipment[];
  onRowClick?: (shipment: Shipment) => void;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function ShipmentList({ shipments, onRowClick }: ShipmentListProps) {
  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>配送ID</TableHead>
            <TableHead>宛先</TableHead>
            <TableHead>商品数</TableHead>
            <TableHead>伝票番号</TableHead>
            <TableHead>作成日</TableHead>
            <TableHead>ステータス</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shipments.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                該当する配送がありません
              </TableCell>
            </TableRow>
          ) : (
            shipments.map((shipment) => (
              <TableRow
                key={shipment.id}
                className="cursor-pointer hover:bg-accent/50"
                onClick={() => onRowClick?.(shipment)}
              >
                <TableCell>
                  <div className="font-medium">{shipment.id.slice(0, 8)}</div>
                </TableCell>
                <TableCell>
                  <div>{shipment.customer_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {shipment.customer_address}
                  </div>
                </TableCell>
                <TableCell>{shipment.items.length}点</TableCell>
                <TableCell>{shipment.tracking_number || "-"}</TableCell>
                <TableCell>{formatDate(shipment.created_at)}</TableCell>
                <TableCell>
                  <StatusBadge status={shipment.status} />
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
