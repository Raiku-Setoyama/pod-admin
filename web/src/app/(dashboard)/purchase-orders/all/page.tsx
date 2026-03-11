"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { ArrowLeft, Download, FileText, Package, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { AllManufacturerOrderList } from "@/features/purchase-orders/components/all-manufacturer-order-list";
import { AllManufacturerOrderFilters } from "@/features/purchase-orders/components/all-manufacturer-order-filters";
import { useAllManufacturerOrderItems } from "@/features/purchase-orders/hooks/use-manufacturer-orders";
import { useManufacturers } from "@/features/manufacturers/hooks/use-manufacturers";
import { apiClient } from "@/lib/api/client";
import { getManufacturerOrderStatusUpdateOptions } from "@/constants/status";
import type { AllManufacturerOrderItem } from "@/types/api";

// デバウンスフック
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

const productTypeLabels: Record<string, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  tshirt: "Tシャツ",
};

const statusLabels: Record<string, string> = {
  ordered: "発注済み",
  manufacturing: "製造中",
  delivered: "納入済",
  shipped: "配送完了",
};

function formatDateForCSV(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatDateTimeForCSV(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const statusUpdateOptions = getManufacturerOrderStatusUpdateOptions();
type ManufacturerOrderStatus = "ordered" | "manufacturing" | "delivered";

// 選択されたアイテムをメーカーごとにグループ化
function groupItemsByManufacturer(
  items: AllManufacturerOrderItem[],
  selectedIds: string[]
): Map<string, { manufacturerId: string; manufacturerName: string; itemIds: string[] }> {
  const grouped = new Map<string, { manufacturerId: string; manufacturerName: string; itemIds: string[] }>();

  for (const item of items) {
    if (selectedIds.includes(item.id)) {
      const existing = grouped.get(item.manufacturer_id);
      if (existing) {
        existing.itemIds.push(item.id);
      } else {
        grouped.set(item.manufacturer_id, {
          manufacturerId: item.manufacturer_id,
          manufacturerName: item.manufacturer_name,
          itemIds: [item.id],
        });
      }
    }
  }

  return grouped;
}

export default function AllPurchaseOrdersPage() {
  const router = useRouter();

  // フィルター状態
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [manufacturerId, setManufacturerId] = useState<string | null>(null);
  const [productType, setProductType] = useState<string | null>(null);
  const [orderedFrom, setOrderedFrom] = useState("");
  const [orderedTo, setOrderedTo] = useState("");
  const [expectedDeliveryRange, setExpectedDeliveryRange] = useState<DateRange | undefined>(undefined);

  // 選択状態
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // ダイアログ・ローディング状態
  const [isStatusDialogOpen, setIsStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState<ManufacturerOrderStatus>("manufacturing");
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [isGeneratingInvoice, setIsGeneratingInvoice] = useState(false);

  // デバウンスされた検索値（300ms）
  const debouncedSearch = useDebounce(search, 300);

  // メーカー一覧取得（フィルター用）
  const { manufacturers } = useManufacturers({ limit: 100 });

  const { data, isLoading, isFiltering, mutate } = useAllManufacturerOrderItems({
    search: debouncedSearch || undefined,
    status: status || undefined,
    manufacturer_id: manufacturerId || undefined,
    product_type: productType || undefined,
    ordered_from: orderedFrom || undefined,
    ordered_to: orderedTo || undefined,
    expected_delivery_from: expectedDeliveryRange?.from ? format(expectedDeliveryRange.from, "yyyy-MM-dd") : undefined,
    expected_delivery_to: expectedDeliveryRange?.to ? format(expectedDeliveryRange.to, "yyyy-MM-dd") : undefined,
  });

  const handleFilterReset = () => {
    setSearch("");
    setStatus(null);
    setManufacturerId(null);
    setProductType(null);
    setOrderedFrom("");
    setOrderedTo("");
    setExpectedDeliveryRange(undefined);
  };

  // CSV出力関数
  const handleExportCSV = useCallback(() => {
    if (!data) return;

    // 選択されたアイテム、または全アイテムを対象
    const itemsToExport = selectedIds.length > 0
      ? data.items.filter((item) => selectedIds.includes(item.id))
      : data.items;

    if (itemsToExport.length === 0) return;

    // CSVヘッダー
    const headers = [
      "メーカー名",
      "注文番号",
      "製品番号",
      "商品名",
      "商品タイプ",
      "ステータス",
      "数量",
      "単価",
      "金額",
      "納品予定日",
      "受注日",
    ];

    // CSVデータ行
    const rows = itemsToExport.map((item: AllManufacturerOrderItem) => [
      item.manufacturer_name,
      item.order_number,
      item.uid || "",
      item.product_name,
      productTypeLabels[item.product_type] || item.product_type,
      statusLabels[item.status] || item.status,
      item.quantity.toString(),
      item.price.toString(),
      (item.price * item.quantity).toString(),
      formatDateForCSV(item.expected_delivery_date),
      formatDateTimeForCSV(item.ordered_at),
    ]);

    // CSV文字列生成（BOM付きUTF-8でExcel対応）
    const csvContent = [
      headers.join(","),
      ...rows.map((row) =>
        row.map((cell) => `"${cell.replace(/"/g, '""')}"`).join(",")
      ),
    ].join("\n");

    const bom = "\uFEFF";
    const blob = new Blob([bom + csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `発注明細_${format(new Date(), "yyyyMMdd_HHmmss")}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [data, selectedIds]);

  // 請求書発行（メーカーごとにAPIを呼び出し）
  const handleGenerateInvoice = useCallback(async () => {
    if (!data || selectedIds.length === 0) return;

    const grouped = groupItemsByManufacturer(data.items, selectedIds);
    if (grouped.size === 0) return;

    setIsGeneratingInvoice(true);
    try {
      const token = localStorage.getItem("access_token");
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

      for (const [, group] of grouped) {
        const response = await fetch(
          `${apiUrl}/manufacturers/${group.manufacturerId}/invoices`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ order_item_ids: group.itemIds }),
          }
        );

        if (!response.ok) {
          throw new Error(`${group.manufacturerName}の請求書発行に失敗しました`);
        }

        const blob = await response.blob();
        const contentDisposition = response.headers.get("Content-Disposition");
        let filename = `${group.manufacturerName}_請求書.pdf`;
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename\*=UTF-8''(.+)/);
          if (filenameMatch) {
            filename = decodeURIComponent(filenameMatch[1]);
          }
        }

        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      toast.success(`${grouped.size}件のメーカーの請求書を発行しました`);
    } catch (error) {
      console.error("Invoice generation failed:", error);
      toast.error(error instanceof Error ? error.message : "請求書発行に失敗しました");
    } finally {
      setIsGeneratingInvoice(false);
    }
  }, [data, selectedIds]);

  // 発注資料ダウンロード（メーカーごとにAPIを呼び出し）
  const handleDownloadDocuments = useCallback(async () => {
    if (!data || selectedIds.length === 0) return;

    const grouped = groupItemsByManufacturer(data.items, selectedIds);
    if (grouped.size === 0) return;

    setIsDownloading(true);
    try {
      const token = localStorage.getItem("access_token");
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

      for (const [, group] of grouped) {
        const params = new URLSearchParams();
        params.set("order_item_ids", group.itemIds.join(","));

        const response = await fetch(
          `${apiUrl}/manufacturers/${group.manufacturerId}/order-documents?${params}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );

        if (!response.ok) {
          throw new Error(`${group.manufacturerName}の発注資料ダウンロードに失敗しました`);
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `TAPI_${group.manufacturerName}_発注資料.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      toast.success(`${grouped.size}件のメーカーの発注資料をダウンロードしました`);
    } catch (error) {
      console.error("Download failed:", error);
      toast.error(error instanceof Error ? error.message : "発注資料のダウンロードに失敗しました");
    } finally {
      setIsDownloading(false);
    }
  }, [data, selectedIds]);

  // ステータス更新（メーカーごとにAPIを呼び出し）
  const handleStatusUpdate = useCallback(async () => {
    if (!data || selectedIds.length === 0) return;

    const grouped = groupItemsByManufacturer(data.items, selectedIds);
    if (grouped.size === 0) return;

    setIsUpdating(true);
    try {
      let totalUpdated = 0;
      let totalShipmentsCreated = 0;

      for (const [, group] of grouped) {
        const result = await apiClient<{ updated_count: number; shipments_created: number }>(
          `/manufacturers/${group.manufacturerId}/order-status`,
          {
            method: "PATCH",
            body: {
              status: newStatus,
              order_item_ids: group.itemIds,
            },
          }
        );
        totalUpdated += result.updated_count;
        totalShipmentsCreated += result.shipments_created;
      }

      if (totalUpdated === 0) {
        toast.warning("更新対象の明細がありませんでした", {
          description: "選択した明細は既に同じステータスか、更新対象外です",
        });
      } else if (newStatus === "delivered" && totalShipmentsCreated > 0) {
        toast.success(`${totalUpdated}件を納入済みに更新し、${totalShipmentsCreated}件の配送が配送リストに追加されました`, {
          description: "配送ステータス: 配送準備中",
          action: {
            label: "配送リストを見る",
            onClick: () => (window.location.href = "/shipments"),
          },
        });
      } else {
        const statusLabel = statusUpdateOptions.find((opt) => opt.value === newStatus)?.label;
        toast.success(`${totalUpdated}件のステータスを「${statusLabel}」に更新しました`);
      }

      setIsStatusDialogOpen(false);
      setSelectedIds([]);
      mutate();
    } catch (error) {
      console.error("Status update failed:", error);
      toast.error("ステータス更新に失敗しました");
    } finally {
      setIsUpdating(false);
    }
  }, [data, selectedIds, newStatus, mutate]);

  // メーカー一覧をフィルターコンポーネント用に変換
  const manufacturerOptions = manufacturers.map((m) => ({
    id: m.id,
    name: m.name,
  }));

  // 初回ロード時のみ全画面ローディングを表示
  if (isLoading && !data) {
    return (
      <PageContainer title="すべての発注" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  const displayData = data ?? {
    items: [],
    total: 0,
    total_quantity: 0,
    total_amount: 0,
  };

  return (
    <PageContainer
      title="すべての発注"
      description="全メーカーの発注明細を横断的に表示"
      actions={
        <Button
          variant="outline"
          onClick={() => router.push("/purchase-orders")}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          発注一覧に戻る
        </Button>
      }
    >
      <div className="space-y-4">
        {/* サマリー */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Package className="h-5 w-5" />
                すべての発注明細
              </CardTitle>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  onClick={handleExportCSV}
                  disabled={displayData.items.length === 0}
                >
                  <Download className="h-4 w-4 mr-2" />
                  CSVダウンロード{selectedIds.length > 0 ? `（${selectedIds.length}件）` : ""}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleGenerateInvoice}
                  disabled={selectedIds.length === 0 || isGeneratingInvoice}
                >
                  <FileText className="h-4 w-4 mr-2" />
                  {isGeneratingInvoice ? "発行中..." : "請求書発行"}
                </Button>
                <Button
                  variant="outline"
                  onClick={handleDownloadDocuments}
                  disabled={selectedIds.length === 0 || isDownloading}
                >
                  <Download className="h-4 w-4 mr-2" />
                  {isDownloading ? "ダウンロード中..." : "発注資料"}
                </Button>
                <Button
                  onClick={() => setIsStatusDialogOpen(true)}
                  disabled={selectedIds.length === 0}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  ステータス更新
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-muted-foreground">明細数</dt>
                <dd className="text-2xl font-bold">{displayData.total}件</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">合計数量</dt>
                <dd className="text-2xl font-bold">{displayData.total_quantity}点</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* フィルター */}
        <AllManufacturerOrderFilters
          search={search}
          status={status}
          manufacturerId={manufacturerId}
          productType={productType}
          orderedFrom={orderedFrom}
          orderedTo={orderedTo}
          expectedDeliveryRange={expectedDeliveryRange}
          onSearchChange={setSearch}
          onStatusChange={setStatus}
          onManufacturerIdChange={setManufacturerId}
          onProductTypeChange={setProductType}
          onOrderedFromChange={setOrderedFrom}
          onOrderedToChange={setOrderedTo}
          onExpectedDeliveryRangeChange={setExpectedDeliveryRange}
          onReset={handleFilterReset}
          manufacturers={manufacturerOptions}
        />

        {/* テーブル */}
        <AllManufacturerOrderList
          data={displayData}
          isLoading={isFiltering}
          selectedIds={selectedIds}
          onSelectChange={setSelectedIds}
        />
      </div>

      {/* ステータス更新ダイアログ */}
      <Dialog open={isStatusDialogOpen} onOpenChange={setIsStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ステータス一括更新</DialogTitle>
            <DialogDescription>
              選択された{selectedIds.length}件の明細のステータスを更新します。
              {data && (() => {
                const grouped = groupItemsByManufacturer(data.items, selectedIds);
                if (grouped.size > 1) {
                  return ` （${grouped.size}件のメーカーにまたがっています）`;
                }
                return "";
              })()}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Select
              value={newStatus}
              onValueChange={(v) => setNewStatus(v as ManufacturerOrderStatus)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {statusUpdateOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsStatusDialogOpen(false)}
            >
              キャンセル
            </Button>
            <Button onClick={handleStatusUpdate} disabled={isUpdating}>
              {isUpdating ? "更新中..." : "一括更新"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PageContainer>
  );
}
