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
import type { ShipmentOrPendingOrder } from "@/types/api";
import { isPendingOrder, isShipment } from "@/types/api";

interface ShipmentListProps {
  shipments: ShipmentOrPendingOrder[];
  onRowClick?: (item: ShipmentOrPendingOrder) => void;
  selectedIds: Set<string>;
  onSelectChange: (ids: Set<string>) => void;
}

// Helper to get the unique ID for each item
function getItemId(item: ShipmentOrPendingOrder): string {
  if (isPendingOrder(item)) {
    return `pending_${item.order_id}`;
  }
  return item.id;
}

// Helper to get customer info
function getCustomerInfo(item: ShipmentOrPendingOrder): { name: string; address: string } {
  if (isPendingOrder(item)) {
    return { name: item.customer_name, address: item.customer_address };
  }
  return { name: item.customer_name, address: item.customer_full_address };
}

// Helper to get item count
function getItemCount(item: ShipmentOrPendingOrder): number {
  if (isPendingOrder(item)) {
    return item.item_count;
  }
  return item.items.length;
}

// Helper to get tracking number (only for shipments)
function getTrackingNumber(item: ShipmentOrPendingOrder): string {
  if (isPendingOrder(item)) {
    return "-";
  }
  return item.tracking_number || "-";
}

// Helper to get display ID
function getDisplayId(item: ShipmentOrPendingOrder): string {
  if (isPendingOrder(item)) {
    return item.order_number;
  }
  return item.id.slice(0, 8);
}

function getEstimatedShippingDate(item: ShipmentOrPendingOrder): string {
  const dateStr = "estimated_shipping_date" in item ? item.estimated_shipping_date : null;
  if (!dateStr) return "-";
  const d = new Date(dateStr);
  return d.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
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
      onSelectChange(new Set(shipments.map((item) => getItemId(item))));
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
            <TableHead>配送予定日</TableHead>
            <TableHead>ステータス</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {shipments.length === 0 ? (
            <TableRow>
              <TableCell colSpan={8} className="h-24 text-center text-muted-foreground">
                該当する配送がありません
              </TableCell>
            </TableRow>
          ) : (
            shipments.map((item) => {
              const itemId = getItemId(item);
              const customerInfo = getCustomerInfo(item);
              return (
                <TableRow
                  key={itemId}
                  className="cursor-pointer hover:bg-accent/50"
                  onClick={() => onRowClick?.(item)}
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <Checkbox
                      checked={selectedIds.has(itemId)}
                      onCheckedChange={(checked) =>
                        handleItemSelect(itemId, !!checked)
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <div className="font-medium">{getDisplayId(item)}</div>
                  </TableCell>
                  <TableCell>
                    <div>{customerInfo.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {customerInfo.address}
                    </div>
                  </TableCell>
                  <TableCell>{getItemCount(item)}点</TableCell>
                  <TableCell>{getTrackingNumber(item)}</TableCell>
                  <TableCell>{formatDate(item.created_at)}</TableCell>
                  <TableCell>{getEstimatedShippingDate(item)}</TableCell>
                  <TableCell>
                    <StatusBadge status={item.status} />
                  </TableCell>
                </TableRow>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
