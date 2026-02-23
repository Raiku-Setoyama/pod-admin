"use client";

import { useState } from "react";
import { toast } from "sonner";
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

// 一括更新可能なステータス（shippedは除外）
type BulkUpdateStatus = "ordered" | "manufacturing" | "delivered";

interface OrderBulkStatusUpdateDialogProps {
  selectedIds: string[];
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function OrderBulkStatusUpdateDialog({
  selectedIds,
  open,
  onClose,
  onSuccess,
}: OrderBulkStatusUpdateDialogProps) {
  const [bulkNewStatus, setBulkNewStatus] = useState<BulkUpdateStatus>("manufacturing");
  const [isUpdating, setIsUpdating] = useState(false);

  const handleBulkStatusUpdate = async () => {
    setIsUpdating(true);
    try {
      const response = await apiClient<{ updated_count: number; failed_count: number; failed_ids: string[] }>("/orders/bulk-status", {
        method: "PATCH",
        body: {
          order_ids: selectedIds,
          status: bulkNewStatus,
        },
      });

      if (response.updated_count > 0) {
        toast.success(`${response.updated_count}件のステータスを更新しました`);
      }
      if (response.failed_count > 0) {
        toast.warning(`${response.failed_count}件は更新できませんでした（ステータス遷移不可）`);
      }
      if (response.updated_count === 0 && response.failed_count > 0) {
        toast.error("全ての更新に失敗しました");
      }

      onClose();
      onSuccess();
    } catch (error) {
      console.error("Status update failed:", error);
      toast.error("ステータス更新に失敗しました");
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>受注ステータス一括更新</DialogTitle>
          <DialogDescription>
            選択された{selectedIds.length}件の受注ステータスを更新します。
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <Select
            value={bulkNewStatus}
            onValueChange={(v) => setBulkNewStatus(v as BulkUpdateStatus)}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ordered">受注済み</SelectItem>
              <SelectItem value="manufacturing">製造中</SelectItem>
              <SelectItem value="delivered">配送準備完了</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            キャンセル
          </Button>
          <Button onClick={handleBulkStatusUpdate} disabled={isUpdating}>
            {isUpdating ? "更新中..." : "更新"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
