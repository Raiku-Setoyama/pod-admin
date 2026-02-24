"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";
import type { OrderSource } from "@/types/api";

interface OrderSourceDeleteDialogProps {
  open: boolean;
  orderSource: OrderSource;
  onClose: () => void;
  onSuccess: () => void;
}

export function OrderSourceDeleteDialog({
  open,
  orderSource,
  onClose,
  onSuccess,
}: OrderSourceDeleteDialogProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    try {
      await apiClient(`/order-sources/${orderSource.id}`, {
        method: "DELETE",
      });
      onSuccess();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "削除に失敗しました";
      setError(message);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>確認</DialogTitle>
          <DialogDescription>
            「{orderSource.name}」を本当に取り除きますか？この操作は元に戻せません。
          </DialogDescription>
        </DialogHeader>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-600">
            エラー: {error}
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={onClose}>
            キャンセル
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? "削除中..." : "削除"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
