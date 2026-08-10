"use client";

import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
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
import type { ShipmentOrPendingOrder, ShipmentSortBy, ShipmentSortOrder } from "@/types/api";
import { isPendingOrder } from "@/types/api";

interface ShipmentListProps {
  shipments: ShipmentOrPendingOrder[];
  onRowClick?: (item: ShipmentOrPendingOrder) => void;
  selectedIds: Set<string>;
  onSelectChange: (ids: Set<string>) => void;
  sortBy?: ShipmentSortBy;
  sortOrder?: ShipmentSortOrder;
  /** 渡されたときだけ列見出しが並び替えボタンになる */
  onSortChange?: (sortBy: ShipmentSortBy, sortOrder: ShipmentSortOrder) => void;
}

interface SortableHeadProps {
  column: ShipmentSortBy;
  label: string;
  sortBy?: ShipmentSortBy;
  sortOrder: ShipmentSortOrder;
  onSortChange?: (sortBy: ShipmentSortBy, sortOrder: ShipmentSortOrder) => void;
}

/**
 * 並び替えできる列見出し（REQ-0049）。
 *
 * 選択中の列は向きの矢印を出し、`aria-sort` でも判別できるようにする。
 * 別の列を押すと昇順から始め、選択中の列を押すと向きが入れ替わる。
 */
function SortableHead({ column, label, sortBy, sortOrder, onSortChange }: SortableHeadProps) {
  if (!onSortChange) {
    return <TableHead>{label}</TableHead>;
  }

  const isActive = sortBy === column;
  const nextOrder: ShipmentSortOrder = isActive && sortOrder === "asc" ? "desc" : "asc";
  const Icon = isActive ? (sortOrder === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;

  return (
    <TableHead aria-sort={isActive ? (sortOrder === "asc" ? "ascending" : "descending") : "none"}>
      <button
        type="button"
        onClick={() => onSortChange(column, nextOrder)}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        <Icon
          aria-hidden="true"
          className={isActive ? "h-3.5 w-3.5" : "h-3.5 w-3.5 text-muted-foreground/50"}
        />
      </button>
    </TableHead>
  );
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

// Helper to get order numbers
function getOrderNumbers(item: ShipmentOrPendingOrder): string[] {
  if (isPendingOrder(item)) {
    return [item.order_number];
  }
  const numbers = item.items
    .map((i) => i.order_number)
    .filter((n): n is string => n != null);
  return [...new Set(numbers)];
}

// Helper to get display ID
function getDisplayId(item: ShipmentOrPendingOrder): string {
  if (isPendingOrder(item)) {
    return item.order_number;
  }
  return item.id.slice(0, 8);
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

function formatDateOnly(dateString: string | null): string {
  if (!dateString) return "-";
  const date = new Date(dateString + "T00:00:00");
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
  sortBy,
  sortOrder = "desc",
  onSortChange,
}: ShipmentListProps) {
  const sortProps = { sortBy, sortOrder, onSortChange };

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
            <SortableHead column="order_number" label="注文番号" {...sortProps} />
            <SortableHead column="customer_name" label="宛先" {...sortProps} />
            <TableHead>商品数</TableHead>
            <TableHead>伝票番号</TableHead>
            <SortableHead column="created_at" label="作成日" {...sortProps} />
            <SortableHead column="estimated_shipping_date" label="配送予定日" {...sortProps} />
            <SortableHead column="status" label="ステータス" {...sortProps} />
          </TableRow>
        </TableHeader>
        <TableBody>
          {shipments.length === 0 ? (
            <TableRow>
              <TableCell colSpan={9} className="h-24 text-center text-muted-foreground">
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
                    <div className="text-xs space-y-0.5">
                      {getOrderNumbers(item).map((num) => (
                        <div key={num}>{num}</div>
                      ))}
                    </div>
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
                  <TableCell>{formatDateOnly(item.estimated_shipping_date)}</TableCell>
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
