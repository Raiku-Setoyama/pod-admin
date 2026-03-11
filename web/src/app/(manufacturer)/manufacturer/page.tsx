"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Checkbox } from "@/components/ui/checkbox";
import {
  useManufacturerOrderItems,
  downloadAllOrderDocuments,
} from "@/features/manufacturer-portal/hooks/use-manufacturer-orders";
import { ManufacturerOrderFilters } from "@/features/purchase-orders/components/manufacturer-order-filters";
import { InvoiceDialog } from "@/features/invoice";
import { Loader2, Package, Download } from "lucide-react";
import type { OrderStatus } from "@/types/api";

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

export default function ManufacturerDashboardPage() {
  const [manufacturerName, setManufacturerName] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // フィルター状態
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<OrderStatus | null>(null);

  const { items, total, totalQuantity, isLoading, isFiltering } = useManufacturerOrderItems({
    search: search || undefined,
    status,
  });

  useEffect(() => {
    const name = localStorage.getItem("manufacturer_name");
    setManufacturerName(name);
  }, []);

  const handleDownloadAll = async () => {
    setIsDownloading(true);
    try {
      const orderItemIds = selectedIds.size > 0 ? Array.from(selectedIds) : undefined;
      const blob = await downloadAllOrderDocuments(
        {
          search: search || undefined,
          status,
        },
        orderItemIds
      );
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `TAPI_${manufacturerName}_発注資料.zip`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleFilterReset = () => {
    setSearch("");
    setStatus(null);
  };

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds(new Set(items.map((item) => item.id)));
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

  const isAllSelected = items.length > 0 && selectedIds.size === items.length;
  const isSomeSelected = selectedIds.size > 0 && !isAllSelected;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">{manufacturerName} 様</h2>
          <p className="text-muted-foreground">
            発注中のアイテム一覧を確認し、製造データをダウンロードできます
          </p>
        </div>
        <div className="flex items-center gap-2">
          <InvoiceDialog
            selectedItemIds={Array.from(selectedIds)}
            isPortal={true}
            disabled={total === 0}
          />
          <Button
            onClick={handleDownloadAll}
            disabled={isDownloading || selectedIds.size === 0}
          >
            <Download className="h-4 w-4 mr-2" />
            {isDownloading
              ? "ダウンロード中..."
              : selectedIds.size > 0
                ? `選択した${selectedIds.size}件をダウンロード`
                : "発注資料"}
          </Button>
        </div>
      </div>

      {/* サマリーカード */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              発注アイテム数
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total}件</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              合計数量
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalQuantity}個</div>
          </CardContent>
        </Card>
      </div>

      {/* 発注アイテム一覧 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            発注中アイテム一覧
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* フィルター */}
          <ManufacturerOrderFilters
            search={search}
            status={status}
            onSearchChange={setSearch}
            onStatusChange={setStatus}
            onReset={handleFilterReset}
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
                  <TableHead>注文日</TableHead>
                  <TableHead>注文番号</TableHead>
                  <TableHead>製品番号</TableHead>
                  <TableHead>商品名</TableHead>
                  <TableHead className="text-center">個数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading || isFiltering ? (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="h-24 text-center text-muted-foreground"
                    >
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        読み込み中...
                      </div>
                    </TableCell>
                  </TableRow>
                ) : items.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="h-24 text-center text-muted-foreground"
                    >
                      発注中のアイテムはありません
                    </TableCell>
                  </TableRow>
                ) : (
                  items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.has(item.id)}
                          onCheckedChange={(checked) =>
                            handleItemSelect(item.id, !!checked)
                          }
                        />
                      </TableCell>
                      <TableCell>{formatDate(item.ordered_at)}</TableCell>
                      <TableCell className="font-medium">
                        {item.order_number}
                      </TableCell>
                      <TableCell>{item.uid || "-"}</TableCell>
                      <TableCell>{item.product_name}</TableCell>
                      <TableCell className="text-center">{item.quantity}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
