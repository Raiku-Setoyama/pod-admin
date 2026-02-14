"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import { StatusBadge } from "@/components/common/status-badge";
import type { Shipment } from "@/types/api";

interface ShipmentListProps {
  shipments: Shipment[];
  onRowClick?: (shipment: Shipment) => void;
  selectedIds: Set<string>;
  onSelectChange: (ids: Set<string>) => void;
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function ShipmentList({
  shipments,
  onRowClick,
  selectedIds,
  onSelectChange,
}: ShipmentListProps) {
  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      onSelectChange(new Set(shipments.map((s) => s.id)));
    } else {
      onSelectChange(new Set());
    }
  };

  const handleItemSelect = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    onSelectChange(newSelected);
  };

  const isAllSelected = shipments.length > 0 && selectedIds.size === shipments.length;
  const isSomeSelected = selectedIds.size > 0 && !isAllSelected;

  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px]">
              <Checkbox
                checked={isAllSelected}
                ref={(el) => {
                  if (el) {
                    (el as HTMLButtonElement & { indeterminate: boolean }).indeterminate = isSomeSelected;
                  }
                }}
                onCheckedChange={handleSelectAll}
              />
            </TableHead>
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
              <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
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
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={selectedIds.has(shipment.id)}
                    onCheckedChange={(checked) =>
                      handleItemSelect(shipment.id, !!checked)
                    }
                  />
                </TableCell>
                <TableCell>
                  <div className="font-medium">{shipment.id.slice(0, 8)}</div>
                </TableCell>
                <TableCell>
                  <div>{shipment.customer_name}</div>
                  <div className="text-xs text-muted-foreground">
                    {shipment.customer_full_address}
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
