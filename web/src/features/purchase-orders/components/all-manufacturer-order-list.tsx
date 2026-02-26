"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2, Package } from "lucide-react";
import type { AllManufacturerOrderItemListResponse } from "@/types/api";

interface AllManufacturerOrderListProps {
  data: AllManufacturerOrderItemListResponse;
  isLoading?: boolean;
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

const statusVariants: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  ordered: "default",
  manufacturing: "secondary",
  delivered: "outline",
  shipped: "outline",
};

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

export function AllManufacturerOrderList({
  data,
  isLoading = false,
}: AllManufacturerOrderListProps) {
  return (
    <div className="space-y-6">
      {/* サマリーカード */}
      <Card>
        <CardContent className="pt-6">
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">明細数</dt>
              <dd className="text-2xl font-bold">{data.total}件</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">合計数量</dt>
              <dd className="text-2xl font-bold">{data.total_quantity}点</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* 受注明細一覧 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            すべての発注明細 ({data.total}件)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>メーカー名</TableHead>
                  <TableHead>注文番号</TableHead>
                  <TableHead>製品番号</TableHead>
                  <TableHead>商品名</TableHead>
                  <TableHead>商品タイプ</TableHead>
                  <TableHead>ステータス</TableHead>
                  <TableHead className="text-center">数量</TableHead>
                  <TableHead>顧客名</TableHead>
                  <TableHead>受注日</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {isLoading ? (
                  <TableRow>
                    <TableCell
                      colSpan={9}
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
                      colSpan={9}
                      className="h-24 text-center text-muted-foreground"
                    >
                      発注中の明細がありません
                    </TableCell>
                  </TableRow>
                ) : (
                  data.items.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="font-medium">
                        {item.manufacturer_name}
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
                        <Badge variant={statusVariants[item.status] || "default"}>
                          {statusLabels[item.status] || item.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center">
                        {item.quantity}
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
    </div>
  );
}
