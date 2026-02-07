"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { Product, ProductType } from "@/types/api";

interface ProductListProps {
  products: Product[];
  onRowClick?: (product: Product) => void;
}

const productTypeLabels: Record<ProductType, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  mug: "マグカップ",
  tshirt: "Tシャツ",
};

function formatPrice(price: number): string {
  return `¥${price.toLocaleString()}`;
}

export function ProductList({ products, onRowClick }: ProductListProps) {
  return (
    <div className="rounded-lg border border-border bg-white">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>種類</TableHead>
            <TableHead>サイズ/位置/カラー</TableHead>
            <TableHead>メーカー</TableHead>
            <TableHead>原価</TableHead>
            <TableHead>リードタイム</TableHead>
            <TableHead>ステータス</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {products.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                該当する商品がありません
              </TableCell>
            </TableRow>
          ) : (
            products.map((product) => (
              <TableRow
                key={product.id}
                className="cursor-pointer hover:bg-accent/50"
                onClick={() => onRowClick?.(product)}
              >
                <TableCell>
                  <Badge variant="outline">
                    {productTypeLabels[product.product_type]}
                  </Badge>
                </TableCell>
                <TableCell>
                  {[product.size, product.position, product.color].filter(Boolean).join(" / ") || "-"}
                </TableCell>
                <TableCell>{product.manufacturer_name || "-"}</TableCell>
                <TableCell>{formatPrice(product.cost)}</TableCell>
                <TableCell>{product.lead_time_days}日</TableCell>
                <TableCell>
                  <Badge variant={product.is_active ? "default" : "secondary"}>
                    {product.is_active ? "有効" : "無効"}
                  </Badge>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
