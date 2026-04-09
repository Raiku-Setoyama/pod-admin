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
import type { Order, OrderStatus, ShipmentStatus } from "@/types/api";

interface OrderListProps {
  orders: Order[];
  onRowClick?: (order: Order) => void;
  selectedIds?: string[];
  onSelectChange?: (ids: string[]) => void;
}

function getDisplayStatus(order: Order): OrderStatus | ShipmentStatus {
  // Shipmentがある場合はShipmentのステータスを優先表示
  if (order.shipment) {
    return order.shipment.status;
  }
  return order.status;
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

function getOrderSummary(order: Order): { productCount: number; totalQuantity: number; productNames: string } {
  if (order.items && order.items.length > 0) {
    const totalQuantity = order.items.reduce((sum, item) => sum + item.quantity, 0);
    const productNames = order.items.map(item => item.product_name).join(", ");
    return {
      productCount: order.items.length,
      totalQuantity,
      productNames: productNames.length > 30 ? productNames.substring(0, 30) + "..." : productNames,
    };
  }
  // Legacy fallback
  return {
    productCount: 1,
    totalQuantity: order.quantity || 0,
    productNames: order.product_name || "-",
  };
}

export function OrderList({ orders, onRowClick, selectedIds = [], onSelectChange }: OrderListProps) {
  const hasSelection = onSelectChange !== undefined;
  const allSelected = orders.length > 0 && selectedIds.length === orders.length;
  const someSelected = selectedIds.length > 0 && selectedIds.length < orders.length;

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      onSelectChange?.(orders.map((o) => o.id));
    } else {
      onSelectChange?.([]);
    }
  };

  const handleSelectOne = (orderId: string, checked: boolean) => {
    if (checked) {
      onSelectChange?.([...selectedIds, orderId]);
    } else {
      onSelectChange?.(selectedIds.filter((id) => id !== orderId));
    }
  };

  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            {hasSelection && (
              <TableHead className="w-12">
                <Checkbox
                  checked={someSelected ? "indeterminate" : allSelected}
                  onCheckedChange={handleSelectAll}
                  aria-label="すべて選択"
                />
              </TableHead>
            )}
            <TableHead>注文番号</TableHead>
            <TableHead>受注元</TableHead>
            <TableHead>購入者</TableHead>
            <TableHead>商品数</TableHead>
            <TableHead>受注日</TableHead>
            <TableHead>配送予定日</TableHead>
            <TableHead>ステータス</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.length === 0 ? (
            <TableRow>
              <TableCell colSpan={hasSelection ? 8 : 7} className="h-24 text-center text-muted-foreground">
                該当する受注がありません
              </TableCell>
            </TableRow>
          ) : (
            orders.map((order) => {
              const summary = getOrderSummary(order);
              const isSelected = selectedIds.includes(order.id);
              return (
                <TableRow
                  key={order.id}
                  className="cursor-pointer hover:bg-accent/50"
                  onClick={() => onRowClick?.(order)}
                >
                  {hasSelection && (
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Checkbox
                        checked={isSelected}
                        onCheckedChange={(checked) => handleSelectOne(order.id, !!checked)}
                        aria-label={`${order.order_number}を選択`}
                      />
                    </TableCell>
                  )}
                  <TableCell>
                    <div>
                      <div className="font-medium">{order.order_number}</div>
                      <div className="text-xs text-muted-foreground">
                        {summary.productNames}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>{order.source ?? "-"}</TableCell>
                  <TableCell>{order.customer_name}</TableCell>
                  <TableCell>
                    {summary.productCount > 1
                      ? `${summary.productCount}種類 / ${summary.totalQuantity}点`
                      : `${summary.totalQuantity}点`}
                  </TableCell>
                  <TableCell>{formatDate(order.ordered_at)}</TableCell>
                  <TableCell>{formatDateOnly(order.estimated_shipping_date)}</TableCell>
                  <TableCell>
                    <StatusBadge status={getDisplayStatus(order)} />
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
