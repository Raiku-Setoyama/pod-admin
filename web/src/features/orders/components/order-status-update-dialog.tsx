"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiClient } from "@/lib/api/client";
import type { Order, OrderStatus } from "@/types/api";

interface OrderStatusUpdateDialogProps {
  order: Order;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

// Statuses that can be selected manually (shipped is controlled by shipment)
const statusOptions: { value: OrderStatus; label: string }[] = [
  { value: "ordered", label: "受注済み" },
  { value: "manufacturing", label: "製造中" },
  { value: "delivered", label: "配送準備完了" },
];

export function OrderStatusUpdateDialog({
  order,
  open,
  onClose,
  onSuccess,
}: OrderStatusUpdateDialogProps) {
  const [newStatus, setNewStatus] = useState<OrderStatus>(order.status);
  const [isUpdating, setIsUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Check if shipment is already shipped
  const isShipmentShipped = order.shipment?.status === "shipped";

  const handleStatusUpdate = async () => {
    if (newStatus === order.status) {
      onClose();
      return;
    }

    setIsUpdating(true);
    setError(null);

    try {
      await apiClient(`/orders/${order.id}/status`, {
        method: "PATCH",
        body: { status: newStatus },
      });
      onSuccess();
      onClose();
    } catch (err: unknown) {
      if (err && typeof err === "object" && "message" in err) {
        setError(String(err.message));
      } else if (err && typeof err === "object" && "code" in err) {
        if (err.code === "INVALID_STATUS_TRANSITION") {
          setError("このステータス変更は許可されていません。");
        } else {
          setError("ステータスの更新に失敗しました。");
        }
      } else {
        setError("ステータスの更新に失敗しました。");
      }
    } finally {
      setIsUpdating(false);
    }
  };

  const currentStatusLabel =
    statusOptions.find((opt) => opt.value === order.status)?.label ||
    order.status;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>ステータス変更</DialogTitle>
          <DialogDescription>
            発注のステータスを変更します。現在のステータス: {currentStatusLabel}
          </DialogDescription>
        </DialogHeader>

        {isShipmentShipped && (
          <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            この発注の配送は既に発送済みです。ステータスを変更するには、先に配送のステータスを戻してください。
          </div>
        )}

        {error && (
          <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">新しいステータス</label>
            <Select
              value={newStatus}
              onValueChange={(value) => setNewStatus(value as OrderStatus)}
              disabled={isShipmentShipped}
            >
              <SelectTrigger aria-disabled={isShipmentShipped}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            キャンセル
          </Button>
          <Button
            onClick={handleStatusUpdate}
            disabled={isUpdating || isShipmentShipped}
          >
            {isUpdating ? "更新中..." : "更新"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
