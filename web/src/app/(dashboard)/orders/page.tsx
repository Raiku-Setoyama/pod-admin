"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Download, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { downloadFileByPost } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { OrderFilters } from "@/features/orders/components/order-filters";
import { OrderList } from "@/features/orders/components/order-list";
import { OrderBulkStatusUpdateDialog } from "@/features/orders/components/order-bulk-status-update-dialog";
import { useOrders } from "@/features/orders/hooks/use-orders";
import type { Order, OrderStatus, ShipmentStatus } from "@/types/api";

// 表示用ステータス（Shipmentステータスを含む）
type DisplayStatus = OrderStatus | ShipmentStatus;

export default function OrdersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<DisplayStatus | null>(null);

  // 一括更新用state
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isBulkStatusDialogOpen, setIsBulkStatusDialogOpen] = useState(false);

  const { orders, total, isLoading, mutate } = useOrders({
    page,
    limit,
    search,
    status,
  });

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setPage(1);
  };

  const handleRowClick = (order: Order) => {
    router.push(`/orders/${order.id}`);
  };

  const handleBulkUpdateSuccess = () => {
    setSelectedIds([]);
    mutate();
  };

  const handleImageDownload = async () => {
    try {
      const now = new Date();
      const timestamp = now.getFullYear().toString()
        + (now.getMonth() + 1).toString().padStart(2, "0")
        + now.getDate().toString().padStart(2, "0")
        + "_"
        + now.getHours().toString().padStart(2, "0")
        + now.getMinutes().toString().padStart(2, "0")
        + now.getSeconds().toString().padStart(2, "0");
      const filename = `受注画像_${timestamp}.zip`;
      await downloadFileByPost(
        "/orders/download-images",
        { order_ids: selectedIds },
        filename
      );
    } catch {
      toast.error("画像のダウンロードに失敗しました");
    }
  };

  return (
    <PageContainer
      title="受注一覧"
      description="外部販売サイトからの受注情報"
      actions={
        selectedIds.length > 0 ? (
          <>
            <Button variant="outline" onClick={handleImageDownload}>
              <Download className="h-4 w-4 mr-2" />
              イメージ画像ダウンロード
            </Button>
            <Button onClick={() => setIsBulkStatusDialogOpen(true)}>
              <RefreshCw className="h-4 w-4 mr-2" />
              選択した{selectedIds.length}件を更新
            </Button>
          </>
        ) : undefined
      }
    >
      <div className="space-y-4">
        <OrderFilters
          search={search}
          status={status}
          onSearchChange={setSearch}
          onStatusChange={setStatus}
        />

        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <OrderList
              orders={orders}
              onRowClick={handleRowClick}
              selectedIds={selectedIds}
              onSelectChange={setSelectedIds}
            />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={handlePageChange}
              onLimitChange={handleLimitChange}
            />
          </>
        )}
      </div>

      <OrderBulkStatusUpdateDialog
        selectedIds={selectedIds}
        open={isBulkStatusDialogOpen}
        onClose={() => setIsBulkStatusDialogOpen(false)}
        onSuccess={handleBulkUpdateSuccess}
      />
    </PageContainer>
  );
}
