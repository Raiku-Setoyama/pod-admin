"use client";

import { useState } from "react";
import { DateRange } from "react-day-picker";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Download, Factory, Loader2, Package, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/lib/api/client";
import { StatusBadge } from "@/components/common/status-badge";
import {
  ManufacturingRegenerateControls,
  useRegenerateManufacturingData,
} from "@/features/manufacturing-data/regenerate-controls";
import {
  getManufacturerOrderStatusUpdateOptions,
} from "@/constants/status";
import type {
  ManufacturerOrderItem,
  ManufacturerOrderItemListResponse,
  OrderStatus,
} from "@/types/api";
import { ManufacturerOrderFilters } from "./manufacturer-order-filters";
import { InvoiceDialog } from "@/features/invoice";

interface ManufacturerOrderDetailProps {
  data: ManufacturerOrderItemListResponse;
  isLoading?: boolean;
  onStatusUpdate?: () => void;
  // フィルター（新しい形式）
  search: string;
  status: OrderStatus | null;
  dateRange?: DateRange;
  expectedDeliveryRange?: DateRange;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: OrderStatus | null) => void;
  onDateRangeChange?: (range: DateRange | undefined) => void;
  onExpectedDeliveryRangeChange?: (range: DateRange | undefined) => void;
  onFilterReset: () => void;
}

const statusUpdateOptions = getManufacturerOrderStatusUpdateOptions();

type ManufacturerOrderStatus = "ordered" | "manufacturing" | "delivered";

const productTypeLabels: Record<string, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  tshirt: "Tシャツ",
};

/**
 * 発注不可（未 ready）の明細か判定する。
 * 発注準備中（製造データ未準備）はメーカー発注できない。統合前データの防御として
 * 発注済み（ordered）かつ製造データが ready でない場合も発注不可とする。
 */
function isOrderBlocked(item: ManufacturerOrderItem): boolean {
  if (item.status === "preparing_order") return true;
  return (
    item.status === "ordered" &&
    !!item.manufacturing_status &&
    item.manufacturing_status !== "ready"
  );
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

function formatDateShort(dateString: string | null): string {
  if (!dateString) return "-";
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

function formatCurrency(amount: number): string {
  return `¥${amount.toLocaleString("ja-JP")}`;
}

export function ManufacturerOrderDetail({
  data,
  isLoading = false,
  onStatusUpdate,
  search,
  status,
  dateRange,
  expectedDeliveryRange,
  onSearchChange,
  onStatusChange,
  onDateRangeChange,
  onExpectedDeliveryRangeChange,
  onFilterReset,
}: ManufacturerOrderDetailProps) {
  const [isStatusDialogOpen, setIsStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState<ManufacturerOrderStatus>(
    "manufacturing"
  );
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const { regeneratingId, regenerate } = useRegenerateManufacturingData(onStatusUpdate);

  const handleStatusUpdate = async () => {
    setIsUpdating(true);
    try {
      const result = await apiClient<{ updated_count: number; shipments_created: number }>(
        `/manufacturers/${data.manufacturer_id}/order-status`,
        {
          method: "PATCH",
          body: {
            status: newStatus,
            order_item_ids: selectedIds.size > 0 ? Array.from(selectedIds) : undefined,
          },
        }
      );

      const updatedCount = result.updated_count;
      const shipmentsCreated = result.shipments_created;

      if (updatedCount === 0) {
        toast.warning("更新対象の明細がありませんでした", {
          description: "選択した明細は既に同じステータスか、更新対象外です",
        });
      } else if (newStatus === "delivered" && shipmentsCreated > 0) {
        // 納入済みかつShipmentが作成された場合のみ、配送リスト追加の通知
        toast.success(`${updatedCount}件を納入済みに更新し、${shipmentsCreated}件の配送が配送リストに追加されました`, {
          description: "配送ステータス: 配送準備中",
          action: {
            label: "配送リストを見る",
            onClick: () => (window.location.href = "/shipments"),
          },
        });
      } else {
        // その他のステータス更新（納入済みでもShipmentが作成されなかった場合を含む）
        const statusLabel = statusUpdateOptions.find(
          (opt) => opt.value === newStatus
        )?.label;
        toast.success(`${updatedCount}件のステータスを「${statusLabel}」に更新しました`);
      }

      setIsStatusDialogOpen(false);
      setSelectedIds(new Set());
      onStatusUpdate?.();
    } catch (error) {
      console.error("Status update failed:", error);
      toast.error("ステータス更新に失敗しました");
    } finally {
      setIsUpdating(false);
    }
  };

  const handleDownload = async () => {
    setIsDownloading(true);
    try {
      const token = localStorage.getItem("access_token");
      const apiUrl =
        process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

      const params = new URLSearchParams();
      if (selectedIds.size > 0) {
        params.set("order_item_ids", Array.from(selectedIds).join(","));
      }

      const queryString = params.toString();
      const url = `${apiUrl}/manufacturers/${data.manufacturer_id}/order-documents${queryString ? `?${queryString}` : ""}`;

      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (!response.ok) {
        throw new Error("Download failed");
      }
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = `TAPI_${data.manufacturer_name}_発注資料.zip`;
      a.click();
      window.URL.revokeObjectURL(blobUrl);
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  // 発注可能な明細のみ選択対象とする（未ready = 製造データ待ちは発注不可）
  const selectableItems = data.items.filter((item) => !isOrderBlocked(item));

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(selectableItems.map((item) => item.id)));
    } else {
      setSelectedIds(new Set());
    }
  };

  const handleItemSelect = (id: string, checked: boolean) => {
    const newSelected = new Set(selectedIds);
    if (checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedIds(newSelected);
  };

  const isAllSelected =
    selectableItems.length > 0 && selectedIds.size === selectableItems.length;
  const isSomeSelected = selectedIds.size > 0 && !isAllSelected;

  return (
    <div className="space-y-6">
      {/* メーカー情報 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Factory className="h-5 w-5" />
              {data.manufacturer_name}
            </CardTitle>
            <div className="flex items-center gap-2">
              <InvoiceDialog
                manufacturerId={data.manufacturer_id}
                selectedItemIds={Array.from(selectedIds)}
                disabled={selectedIds.size === 0}
              />
              <Button
                variant="outline"
                onClick={handleDownload}
                disabled={isDownloading || selectedIds.size === 0}
              >
                <Download className="h-4 w-4 mr-2" />
                {isDownloading ? "ダウンロード中..." : "発注資料"}
              </Button>
              <Button
                onClick={() => setIsStatusDialogOpen(true)}
                disabled={selectedIds.size === 0}
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
              <dt className="text-sm text-muted-foreground">発注中明細数</dt>
              <dd className="text-2xl font-bold">{data.total}件</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">合計数量</dt>
              <dd className="text-2xl font-bold">{data.total_quantity}点</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* 発注中受注明細一覧 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            発注中の受注明細 ({data.total}件)
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* フィルター */}
          <ManufacturerOrderFilters
            search={search}
            status={status}
            dateRange={dateRange}
            expectedDeliveryRange={expectedDeliveryRange}
            onSearchChange={onSearchChange}
            onStatusChange={onStatusChange}
            onDateRangeChange={onDateRangeChange}
            onExpectedDeliveryRangeChange={onExpectedDeliveryRangeChange}
            onReset={onFilterReset}
          />

          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[50px]">
                    <Checkbox
                      checked={isAllSelected}
                      ref={(el) => {
                        if (el) {
                          (el as HTMLButtonElement & { indeterminate: boolean }).indeterminate = isSomeSelected;
                        }
                      }}
                      onCheckedChange={handleSelectAll}
                    />
                  </TableHead>
                  <TableHead>注文番号</TableHead>
                  <TableHead>製品番号</TableHead>
                  <TableHead>商品名</TableHead>
                  <TableHead>商品タイプ</TableHead>
                  <TableHead>ステータス</TableHead>
                  <TableHead className="text-center">数量</TableHead>
                  <TableHead className="text-right">単価</TableHead>
                  <TableHead className="text-right">金額</TableHead>
                  <TableHead>納品予定日</TableHead>
                  <TableHead>受注日</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell
                      colSpan={11}
                      className="h-24 text-center text-muted-foreground"
                    >
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        読み込み中...
                      </div>
                    </TableCell>
                  </TableRow>
                ) : data.items.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={11}
                      className="h-24 text-center text-muted-foreground"
                    >
                      発注中の明細がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  data.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.has(item.id)}
                          disabled={isOrderBlocked(item)}
                          onCheckedChange={(checked) =>
                            handleItemSelect(item.id, !!checked)
                          }
                        />
                      </TableCell>
                      <TableCell className="font-medium">
                        {item.order_number}
                      </TableCell>
                      <TableCell>{item.uid || "-"}</TableCell>
                      <TableCell>{item.product_name}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">
                          {productTypeLabels[item.product_type] ||
                            item.product_type}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <StatusBadge status={item.status} />
                          <ManufacturingRegenerateControls
                            itemStatus={item.status}
                            mfgStatus={item.manufacturing_status}
                            manufacturingDataId={item.manufacturing_data_id}
                            regeneratingId={regeneratingId}
                            onRegenerate={regenerate}
                          />
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        {item.quantity}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(item.price)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatCurrency(item.price * item.quantity)}
                      </TableCell>
                      <TableCell>{formatDateShort(item.expected_delivery_date)}</TableCell>
                      <TableCell>{formatDate(item.ordered_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* ステータス更新ダイアログ */}
      <Dialog open={isStatusDialogOpen} onOpenChange={setIsStatusDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>ステータス一括更新</DialogTitle>
            <DialogDescription>
              {selectedIds.size > 0
                ? `${data.manufacturer_name}の選択された${selectedIds.size}件のステータスを更新します。`
                : `${data.manufacturer_name}の発注中明細${data.total}件のステータスを一括更新します。`}
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
    </div>
  );
}
