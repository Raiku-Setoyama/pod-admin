"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/common/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Download, Package, User, FileText, ShoppingBag, ExternalLink } from "lucide-react";
import { apiClient } from "@/lib/api/client";
import type { Order, OrderItem } from "@/types/api";
import { OrderStatusHistory } from "./order-status-history";

interface OrderDetailProps {
  order: Order;
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

function formatPrice(price: number): string {
  return `¥${price.toLocaleString()}`;
}

function formatProductType(type: string): string {
  const typeMap: Record<string, string> = {
    acrylic_keychain: "アクリルキーホルダー",
    acrylic_stand: "アクリルスタンド",
    sticker: "ステッカー",
    tote_bag: "トートバッグ",
    tshirt: "Tシャツ",
  };
  return typeMap[type] || type;
}

export function OrderDetail({ order }: OrderDetailProps) {
  const handleDownloadManufacturingData = async () => {
    try {
      const data = await apiClient<Blob>(`/orders/${order.id}/manufacturing-data`);

      const blob = new Blob([data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = order.manufacturing_data?.filename || `${order.order_number}_data`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Download failed:", error);
    }
  };

  // Calculate total from items or use total_price
  const totalQuantity = order.items?.reduce((sum, item) => sum + item.quantity, 0) || order.quantity || 0;

  return (
    <div className="space-y-6">
      {/* ステータスと基本情報 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <Package className="h-5 w-5" />
              受注情報
            </CardTitle>
            <StatusBadge status={order.status} />
          </div>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">注文番号</dt>
              <dd className="font-medium">{order.order_number}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">受注日時</dt>
              <dd className="font-medium">{formatDate(order.ordered_at)}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">商品数</dt>
              <dd className="font-medium">{order.items?.length || 1}種類 / {totalQuantity}点</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">合計金額</dt>
              <dd className="font-medium text-lg">
                {formatPrice(order.total_price)}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* 商品一覧 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ShoppingBag className="h-5 w-5" />
            商品一覧
          </CardTitle>
        </CardHeader>
        <CardContent>
          {order.items && order.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16">画像</TableHead>
                  <TableHead>外部ID</TableHead>
                  <TableHead>商品名</TableHead>
                  <TableHead>種別</TableHead>
                  <TableHead>サイズ</TableHead>
                  <TableHead>色</TableHead>
                  <TableHead>位置</TableHead>
                  <TableHead className="text-right">数量</TableHead>
                  <TableHead className="text-right">単価</TableHead>
                  <TableHead className="text-right">小計</TableHead>
                  <TableHead>デザイン</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {order.items.map((item: OrderItem) => (
                  <TableRow key={item.id}>
                    <TableCell>
                      {item.thumbnail_image_url ? (
                        <img
                          src={item.thumbnail_image_url}
                          alt={item.product_name}
                          className="w-12 h-12 object-cover rounded"
                        />
                      ) : (
                        <div className="w-12 h-12 bg-muted rounded flex items-center justify-center">
                          <ShoppingBag className="h-6 w-6 text-muted-foreground" />
                        </div>
                      )}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground font-mono">
                      {item.uid || "-"}
                    </TableCell>
                    <TableCell className="font-medium">{item.product_name}</TableCell>
                    <TableCell>{formatProductType(item.product_type)}</TableCell>
                    <TableCell>{item.size || "-"}</TableCell>
                    <TableCell>{item.color || "-"}</TableCell>
                    <TableCell>{item.position || "-"}</TableCell>
                    <TableCell className="text-right">{item.quantity}</TableCell>
                    <TableCell className="text-right">{formatPrice(item.price)}</TableCell>
                    <TableCell className="text-right font-medium">
                      {formatPrice(item.price * item.quantity)}
                    </TableCell>
                    <TableCell>
                      {item.design_image_url && (
                        <a
                          href={item.design_image_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center text-primary hover:underline"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            // Legacy: 旧形式のデータの場合
            <dl className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-muted-foreground">商品名</dt>
                <dd className="font-medium">{order.product_name || "-"}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">数量</dt>
                <dd className="font-medium">{order.quantity || 0}点</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">単価</dt>
                <dd className="font-medium">{order.price ? formatPrice(order.price) : "-"}</dd>
              </div>
              <div>
                <dt className="text-sm text-muted-foreground">合計金額</dt>
                <dd className="font-medium text-lg">
                  {order.price && order.quantity
                    ? formatPrice(order.price * order.quantity)
                    : formatPrice(order.total_price)}
                </dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>

      {/* 顧客情報 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            顧客情報
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">氏名</dt>
              <dd className="font-medium">{order.customer_name}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">電話番号</dt>
              <dd className="font-medium">{order.customer_phone || "-"}</dd>
            </div>
            <div className="col-span-2">
              <dt className="text-sm text-muted-foreground">住所</dt>
              <dd className="font-medium">
                〒{order.customer_postal_code}
                <br />
                {order.customer_full_address}
              </dd>
            </div>
            <div className="col-span-2">
              <dt className="text-sm text-muted-foreground">メールアドレス</dt>
              <dd className="font-medium">{order.customer_email || "-"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      {/* 製造データ (レガシー) */}
      {order.manufacturing_data?.path && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              製造データ (レガシー)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between p-4 bg-muted rounded-lg">
              <div>
                <p className="font-medium">
                  {order.manufacturing_data.filename || "製造データファイル"}
                </p>
                <p className="text-sm text-muted-foreground">
                  ファイルが添付されています
                </p>
              </div>
              <Button onClick={handleDownloadManufacturingData}>
                <Download className="h-4 w-4 mr-2" />
                ダウンロード
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ステータス履歴 */}
      <OrderStatusHistory orderId={order.id} />

      {/* タイムスタンプ */}
      <Card>
        <CardContent className="pt-6">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">作成日時</dt>
              <dd>{formatDate(order.created_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">更新日時</dt>
              <dd>{formatDate(order.updated_at)}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>

    </div>
  );
}
