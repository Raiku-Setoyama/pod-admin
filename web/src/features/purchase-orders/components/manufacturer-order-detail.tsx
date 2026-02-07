"use client";

import { useState } from "react";
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
import { Download, Factory, Package, RefreshCw } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import type { ManufacturerOrderItemListResponse } from "@/types/api";

interface ManufacturerOrderDetailProps {
  data: ManufacturerOrderItemListResponse;
  onStatusUpdate?: () => void;
}

const statusOptions = [
  { value: "manufacturing", label: "製造中" },
  { value: "delivered", label: "納入済" },
];

const productTypeLabels: Record<string, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  mug: "マグカップ",
  tshirt: "Tシャツ",
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export function ManufacturerOrderDetail({
  data,
  onStatusUpdate,
}: ManufacturerOrderDetailProps) {
  const [isStatusDialogOpen, setIsStatusDialogOpen] = useState(false);
  const [newStatus, setNewStatus] = useState<"manufacturing" | "delivered">(
    "manufacturing"
  );
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleStatusUpdate = async () => {
    setIsUpdating(true);
    try {
      await apiClient(`/manufacturers/${data.manufacturer_id}/order-status`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
        headers: {
          "Content-Type": "application/json",
        },
      });
      setIsStatusDialogOpen(false);
      onStatusUpdate?.();
    } catch (error) {
      console.error("Status update failed:", error);
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
      const response = await fetch(
        `${apiUrl}/manufacturers/${data.manufacturer_id}/order-documents`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        }
      );
      if (!response.ok) {
        throw new Error("Download failed");
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${data.manufacturer_name}_発注資料.zip`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
    } finally {
      setIsDownloading(false);
    }
  };

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
              <Button
                variant="outline"
                onClick={handleDownload}
                disabled={isDownloading || data.total === 0}
              >
                <Download className="h-4 w-4 mr-2" />
                {isDownloading ? "ダウンロード中..." : "発注資料をダウンロード"}
              </Button>
              <Button
                onClick={() => setIsStatusDialogOpen(true)}
                disabled={data.total === 0}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                ステータス一括更新
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-3 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">発注中明細数</dt>
              <dd className="text-2xl font-bold">{data.total}件</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">合計数量</dt>
              <dd className="text-2xl font-bold">{data.total_quantity}点</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">合計金額</dt>
              <dd className="text-2xl font-bold">
                ¥{data.total_amount.toLocaleString()}
              </dd>
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
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>注文番号</TableHead>
                  <TableHead>製品番号</TableHead>
                  <TableHead>商品名</TableHead>
                  <TableHead>商品タイプ</TableHead>
                  <TableHead className="text-center">数量</TableHead>
                  <TableHead className="text-right">金額</TableHead>
                  <TableHead>顧客名</TableHead>
                  <TableHead>受注日</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={8}
                      className="h-24 text-center text-muted-foreground"
                    >
                      発注中の明細がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  data.items.map((item) => (
                    <TableRow key={item.id}>
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
                      <TableCell className="text-center">
                        {item.quantity}
                      </TableCell>
                      <TableCell className="text-right">
                        ¥{(item.price * item.quantity).toLocaleString()}
                      </TableCell>
                      <TableCell>{item.customer_name}</TableCell>
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
              {data.manufacturer_name}の発注中明細{data.total}
              件のステータスを一括更新します。
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Select
              value={newStatus}
              onValueChange={(v) =>
                setNewStatus(v as "manufacturing" | "delivered")
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map((opt) => (
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
