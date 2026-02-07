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
import { LoadingSpinner } from "@/components/common/loading-spinner";
import {
  useManufacturerOrderItems,
  downloadAllOrderDocuments,
} from "@/features/manufacturer-portal/hooks/use-manufacturer-orders";
import { Package, Download } from "lucide-react";

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

export default function ManufacturerDashboardPage() {
  const [manufacturerName, setManufacturerName] = useState<string | null>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const { items, total, totalQuantity, isLoading } =
    useManufacturerOrderItems();

  useEffect(() => {
    const name = localStorage.getItem("manufacturer_name");
    setManufacturerName(name);
  }, []);

  const handleDownloadAll = async () => {
    setIsDownloading(true);
    try {
      const blob = await downloadAllOrderDocuments();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${manufacturerName}_発注資料.zip`;
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">{manufacturerName} 様</h2>
          <p className="text-muted-foreground">
            発注中のアイテム一覧を確認し、製造データをダウンロードできます
          </p>
        </div>
        <Button
          onClick={handleDownloadAll}
          disabled={isDownloading || total === 0}
        >
          <Download className="h-4 w-4 mr-2" />
          {isDownloading ? "ダウンロード中..." : "発注資料をダウンロード"}
        </Button>
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
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner />
            </div>
          ) : items.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              発注中のアイテムはありません
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>注文日</TableHead>
                  <TableHead>注文番号</TableHead>
                  <TableHead>製品番号</TableHead>
                  <TableHead>商品名</TableHead>
                  <TableHead className="text-center">個数</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{formatDate(item.ordered_at)}</TableCell>
                    <TableCell className="font-medium">
                      {item.order_number}
                    </TableCell>
                    <TableCell>{item.uid || "-"}</TableCell>
                    <TableCell>{item.product_name}</TableCell>
                    <TableCell className="text-center">{item.quantity}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
