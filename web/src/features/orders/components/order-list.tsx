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
import type { Order, OrderStatus, ShipmentStatus } from "@/types/api";

interface OrderListProps {
  orders: Order[];
  onRowClick?: (order: Order) => void;
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

export function OrderList({ orders, onRowClick }: OrderListProps) {
  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>注文番号</TableHead>
            <TableHead>受注元</TableHead>
            <TableHead>購入者</TableHead>
            <TableHead>商品数</TableHead>
            <TableHead>受注日</TableHead>
            <TableHead>ステータス</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                該当する受注がありません
              </TableCell>
            </TableRow>
          ) : (
            orders.map((order) => {
              const summary = getOrderSummary(order);
              return (
                <TableRow
                  key={order.id}
                  className="cursor-pointer hover:bg-accent/50"
                  onClick={() => onRowClick?.(order)}
                >
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
