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
  DialogTrigger,
} from "@/components/ui/dialog";
import { FileTextIcon, Loader2Icon } from "lucide-react";
import { toast } from "sonner";
import {
  downloadInvoiceByItems,
  downloadPortalInvoiceByItems,
} from "../api/invoice-api";

interface InvoiceDialogProps {
  manufacturerId?: string;
  selectedItemIds: string[];
  isPortal?: boolean;
  disabled?: boolean;
}

export function InvoiceDialog({
  manufacturerId,
  selectedItemIds,
  isPortal = false,
  disabled = false,
}: InvoiceDialogProps) {
  const [open, setOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerate = async () => {
    if (selectedItemIds.length === 0) {
      toast.error("請求対象を選択してください");
      return;
    }

    setIsLoading(true);
    try {
      if (isPortal) {
        await downloadPortalInvoiceByItems(selectedItemIds);
      } else {
        if (!manufacturerId) {
          toast.error("メーカーIDが指定されていません");
          return;
        }
        await downloadInvoiceByItems(manufacturerId, selectedItemIds);
      }
      toast.success("請求書を発行しました");
      setOpen(false);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "請求書の発行に失敗しました"
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" disabled={disabled}>
          <FileTextIcon className="mr-2 h-4 w-4" />
          請求書発行
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>請求書発行</DialogTitle>
          <DialogDescription>
            選択した明細に対して請求書PDFを発行します。
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          <div className="rounded-md border p-4">
            <p className="text-sm text-muted-foreground">
              選択中の明細: <strong>{selectedItemIds.length}件</strong>
            </p>
            {selectedItemIds.length === 0 && (
              <p className="mt-2 text-sm text-destructive">
                請求対象の明細を選択してください
              </p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            キャンセル
          </Button>
          <Button
            onClick={handleGenerate}
            disabled={isLoading || selectedItemIds.length === 0}
          >
            {isLoading && <Loader2Icon className="mr-2 h-4 w-4 animate-spin" />}
            請求書を発行
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
