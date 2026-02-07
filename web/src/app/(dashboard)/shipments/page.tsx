"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RefreshCw, Upload } from "lucide-react";
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
import { useShipments } from "@/features/shipments/hooks/use-shipments";
import type { Shipment, ShipmentStatus } from "@/types/api";

type SortBy = "created_at" | "shipped_at" | "delivered_at";
type SortOrder = "asc" | "desc";

export default function ShipmentsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  // Filter states
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ShipmentStatus | null>(null);
  const [trackingNumber, setTrackingNumber] = useState("");
  const [carrier, setCarrier] = useState<string | null>(null);
  const [shippedFrom, setShippedFrom] = useState("");
  const [shippedTo, setShippedTo] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");
  const [deliveredFrom, setDeliveredFrom] = useState("");
  const [deliveredTo, setDeliveredTo] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  // 一括更新用state
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [isBulkStatusDialogOpen, setIsBulkStatusDialogOpen] = useState(false);
  const [bulkNewStatus, setBulkNewStatus] = useState<ShipmentStatus>("ready");
  const [isUpdating, setIsUpdating] = useState(false);

  const { shipments, total, isLoading, mutate } = useShipments({
    page,
    limit,
    status,
    search: search || undefined,
    tracking_number: trackingNumber || undefined,
    carrier: carrier || undefined,
    shipped_from: shippedFrom || undefined,
    shipped_to: shippedTo || undefined,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
    delivered_from: deliveredFrom || undefined,
    delivered_to: deliveredTo || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const handleRowClick = (shipment: Shipment) => {
    router.push(`/shipments/${shipment.id}`);
  };

  const handleReset = () => {
    setSearch("");
    setStatus(null);
    setTrackingNumber("");
    setCarrier(null);
    setShippedFrom("");
    setShippedTo("");
    setCreatedFrom("");
    setCreatedTo("");
    setDeliveredFrom("");
    setDeliveredTo("");
    setSortBy("created_at");
    setSortOrder("desc");
    setPage(1);
  };

  const handleSortChange = (newSortBy: SortBy, newSortOrder: SortOrder) => {
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
    setPage(1);
  };

  const handleBulkStatusUpdate = async () => {
    setIsUpdating(true);
    try {
      const response = await apiClient("/shipments/bulk-status", {
        method: "PATCH",
        body: JSON.stringify({
          shipment_ids: Array.from(selectedIds),
          status: bulkNewStatus,
        }),
        headers: { "Content-Type": "application/json" },
      });
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

  return (
    <PageContainer
      title="配送一覧"
      description="配送管理・追跡情報"
      actions={
        <div className="flex gap-2">
          {selectedIds.size > 0 && (
            <Button onClick={() => setIsBulkStatusDialogOpen(true)}>
              <RefreshCw className="h-4 w-4 mr-2" />
              選択した{selectedIds.size}件を更新
            </Button>
          )}
          <Button variant="outline">
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
          trackingNumber={trackingNumber}
          carrier={carrier}
          shippedFrom={shippedFrom}
          shippedTo={shippedTo}
          createdFrom={createdFrom}
          createdTo={createdTo}
          deliveredFrom={deliveredFrom}
          deliveredTo={deliveredTo}
          sortBy={sortBy}
          sortOrder={sortOrder}
          onSearchChange={(value) => { setSearch(value); setPage(1); }}
          onStatusChange={(value) => { setStatus(value); setPage(1); }}
          onTrackingNumberChange={(value) => { setTrackingNumber(value); setPage(1); }}
          onCarrierChange={(value) => { setCarrier(value); setPage(1); }}
          onShippedFromChange={(value) => { setShippedFrom(value); setPage(1); }}
          onShippedToChange={(value) => { setShippedTo(value); setPage(1); }}
          onCreatedFromChange={(value) => { setCreatedFrom(value); setPage(1); }}
          onCreatedToChange={(value) => { setCreatedTo(value); setPage(1); }}
          onDeliveredFromChange={(value) => { setDeliveredFrom(value); setPage(1); }}
          onDeliveredToChange={(value) => { setDeliveredTo(value); setPage(1); }}
          onSortChange={handleSortChange}
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
                <SelectItem value="pending">配送準備中</SelectItem>
                <SelectItem value="ready">配送準備完了</SelectItem>
                <SelectItem value="shipped">発送済み</SelectItem>
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
    </PageContainer>
  );
}
