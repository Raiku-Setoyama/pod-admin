"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Download, RefreshCw, Upload } from "lucide-react";
import { format } from "date-fns";
import { DateRange } from "react-day-picker";
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
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { ShipmentList } from "@/features/shipments/components/shipment-list";
import { ShipmentFilters } from "@/features/shipments/components/shipment-filters";
import { TrackingImport } from "@/features/shipments/components/tracking-import";
import { useShipments } from "@/features/shipments/hooks/use-shipments";
import { getShipmentStatusUpdateOptions } from "@/constants/status";
import type { ShipmentStatus, ShipmentOrPendingOrder, PendingOrderStatus } from "@/types/api";
import { isShipment } from "@/types/api";

const statusOptions = getShipmentStatusUpdateOptions();

type ShipmentFilterStatus = ShipmentStatus | PendingOrderStatus;

export default function ShipmentsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  // Filter states
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ShipmentFilterStatus | null>(null);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);

  // 一括更新用state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkStatusDialogOpen, setIsBulkStatusDialogOpen] = useState(false);
  const [bulkNewStatus, setBulkNewStatus] = useState<ShipmentStatus>("ready");
  const [isUpdating, setIsUpdating] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isDownloadingThumbnails, setIsDownloadingThumbnails] = useState(false);

  // 伝票番号インポート用state
  const [isTrackingImportDialogOpen, setIsTrackingImportDialogOpen] = useState<boolean>(false);
  const [trackingImportKey, setTrackingImportKey] = useState<number>(0);

  const handleTrackingImportOpenChange = (open: boolean) => {
    setIsTrackingImportDialogOpen(open);
    if (!open) {
      setTrackingImportKey((prev) => prev + 1);
    }
  };

  const { shipments, total, isLoading, mutate } = useShipments({
    page,
    limit,
    status,
    search: search || undefined,
    created_from: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
    created_to: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
  });

  // Helper functions to separate selected IDs by type
  const getSelectedShipmentIds = (): string[] => {
    return Array.from(selectedIds)
      .filter((id) => !id.startsWith("pending_"));
  };

  const getSelectedOrderIds = (): string[] => {
    return Array.from(selectedIds)
      .filter((id) => id.startsWith("pending_"))
      .map((id) => id.replace("pending_", ""));
  };

  // Check if any shipments are selected (for bulk status update)
  const hasSelectedShipments = getSelectedShipmentIds().length > 0;

  const handleRowClick = (item: ShipmentOrPendingOrder) => {
    // Only navigate to detail page for actual shipments
    if (isShipment(item)) {
      router.push(`/shipments/${item.id}`);
    } else {
      // For pending orders, navigate to order detail page
      router.push(`/orders/${item.order_id}`);
    }
  };

  const handleReset = () => {
    setSearch("");
    setStatus(null);
    setDateRange(undefined);
    setPage(1);
  };

  const handleBulkStatusUpdate = async () => {
    const shipmentIds = getSelectedShipmentIds();
    if (shipmentIds.length === 0) {
      toast.warning("配送ステータスを更新できるのは配送レコードのみです");
      return;
    }

    setIsUpdating(true);
    try {
      const response = await apiClient("/shipments/bulk-status", {
        method: "PATCH",
        body: {
          shipment_ids: shipmentIds,
          status: bulkNewStatus,
        },
      }) as { updated_count: number; failed_count: number };
      toast.success(`${response.updated_count}件のステータスを更新しました`);
      if (response.failed_count > 0) {
        toast.warning(`${response.failed_count}件は更新できませんでした（ステータス遷移不可）`);
      }
      setIsBulkStatusDialogOpen(false);
      setSelectedIds(new Set());
      mutate();
    } catch (error) {
      console.error("Status update failed:", error);
      toast.error("ステータス更新に失敗しました");
    } finally {
      setIsUpdating(false);
    }
  };

  const handleExportCsv = async () => {
    const shipmentIds = getSelectedShipmentIds();
    const orderIds = getSelectedOrderIds();

    if (shipmentIds.length === 0 && orderIds.length === 0) {
      toast.warning("エクスポートする対象を選択してください");
      return;
    }

    setIsExporting(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

      // Send both shipment_ids and order_ids in a single request
      const response = await fetch(`${apiBaseUrl}/shipments/export-csv`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          shipment_ids: shipmentIds,
          order_ids: orderIds,
        }),
      });

      if (!response.ok) {
        throw new Error("Export failed");
      }

      // Get filename from Content-Disposition header
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = "export.csv";
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
        if (filenameMatch) {
          filename = decodeURIComponent(filenameMatch[1]);
        }
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success(`${selectedIds.size}件のデータをエクスポートしました`);
    } catch (error) {
      console.error("Export failed:", error);
      toast.error("CSVエクスポートに失敗しました");
    } finally {
      setIsExporting(false);
    }
  };

  const handleDownloadThumbnails = async () => {
    const shipmentIds = getSelectedShipmentIds();
    const orderIds = getSelectedOrderIds();

    if (shipmentIds.length === 0 && orderIds.length === 0) {
      toast.warning("ダウンロードする対象を選択してください");
      return;
    }

    setIsDownloadingThumbnails(true);
    try {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

      // Send both shipment_ids and order_ids in a single request
      const response = await fetch(`${apiBaseUrl}/shipments/download-thumbnails`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
        body: JSON.stringify({
          shipment_ids: shipmentIds,
          order_ids: orderIds,
        }),
      });

      if (!response.ok) {
        throw new Error("Download failed");
      }

      // Get filename from Content-Disposition header
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = "thumbnails.zip";
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
        if (filenameMatch) {
          filename = decodeURIComponent(filenameMatch[1]);
        }
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      toast.success(`${selectedIds.size}件のサムネイル画像をダウンロードしました`);
    } catch (error) {
      console.error("Thumbnail download failed:", error);
      toast.error("サムネイル画像のダウンロードに失敗しました");
    } finally {
      setIsDownloadingThumbnails(false);
    }
  };

  return (
    <PageContainer
      title="配送一覧"
      description="配送管理・追跡情報"
      actions={
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={handleExportCsv}
            disabled={isExporting || selectedIds.size === 0}
          >
            <Download className="h-4 w-4 mr-2" />
            {isExporting ? "エクスポート中..." : "受注CSV"}
          </Button>
          <Button
            variant="outline"
            onClick={handleDownloadThumbnails}
            disabled={isDownloadingThumbnails || selectedIds.size === 0}
          >
            <Download className="h-4 w-4 mr-2" />
            {isDownloadingThumbnails ? "ダウンロード中..." : "商品サムネイル"}
          </Button>
          <Button
            onClick={() => setIsBulkStatusDialogOpen(true)}
            disabled={!hasSelectedShipments}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            ステータス更新
          </Button>
          <Button variant="outline" onClick={() => setIsTrackingImportDialogOpen(true)}>
            <Upload className="h-4 w-4" />
            伝票番号インポート
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <ShipmentFilters
          search={search}
          status={status}
          dateRange={dateRange}
          onSearchChange={(value) => { setSearch(value); setPage(1); }}
          onStatusChange={(value) => { setStatus(value); setPage(1); }}
          onDateRangeChange={(range) => { setDateRange(range); setPage(1); }}
          onReset={handleReset}
        />

        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ShipmentList
              shipments={shipments}
              onRowClick={handleRowClick}
              selectedIds={selectedIds}
              onSelectChange={setSelectedIds}
            />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={setPage}
              onLimitChange={(newLimit) => {
                setLimit(newLimit);
                setPage(1);
              }}
            />
          </>
        )}
      </div>

      {/* 配送ステータス一括更新ダイアログ */}
      <Dialog open={isBulkStatusDialogOpen} onOpenChange={setIsBulkStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>配送ステータス一括更新</DialogTitle>
            <DialogDescription>
              選択された{selectedIds.size}件の配送ステータスを更新します。
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Select
              value={bulkNewStatus}
              onValueChange={(v) => setBulkNewStatus(v as ShipmentStatus)}
            >
              <SelectTrigger>
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
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsBulkStatusDialogOpen(false)}
            >
              キャンセル
            </Button>
            <Button onClick={handleBulkStatusUpdate} disabled={isUpdating}>
              {isUpdating ? "更新中..." : "一括更新"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 伝票番号インポートダイアログ */}
      <Dialog open={isTrackingImportDialogOpen} onOpenChange={handleTrackingImportOpenChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>伝票番号インポート</DialogTitle>
            <DialogDescription>
              CSV/XLSXファイルから伝票番号を一括インポートします。
            </DialogDescription>
          </DialogHeader>
          <TrackingImport
            key={trackingImportKey}
            onImportComplete={() => {
              mutate();
            }}
          />
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
