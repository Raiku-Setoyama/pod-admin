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
import { Checkbox } from "@/components/ui/checkbox";
import { Loader2 } from "lucide-react";
import type { AllManufacturerOrderItemListResponse } from "@/types/api";

interface AllManufacturerOrderListProps {
  data: AllManufacturerOrderItemListResponse;
  isLoading?: boolean;
  selectedIds?: string[];
  onSelectChange?: (ids: string[]) => void;
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

export function AllManufacturerOrderList({
  data,
  isLoading = false,
  selectedIds = [],
  onSelectChange,
}: AllManufacturerOrderListProps) {
  const allItemIds = data.items.map((item) => item.id);
  const isAllSelected = allItemIds.length > 0 && allItemIds.every((id) => selectedIds.includes(id));
  const isSomeSelected = allItemIds.some((id) => selectedIds.includes(id)) && !isAllSelected;

  const handleSelectAll = (checked: boolean) => {
    if (!onSelectChange) return;
    if (checked) {
      onSelectChange(allItemIds);
    } else {
      onSelectChange([]);
    }
  };

  const handleSelectItem = (itemId: string, checked: boolean) => {
    if (!onSelectChange) return;
    if (checked) {
      onSelectChange([...selectedIds, itemId]);
    } else {
      onSelectChange(selectedIds.filter((id) => id !== itemId));
    }
  };

  return (
    <div className="rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12">
              <Checkbox
                checked={isSomeSelected ? "indeterminate" : isAllSelected}
                onCheckedChange={handleSelectAll}
                aria-label="全て選択"
              />
            </TableHead>
            <TableHead>メーカー名</TableHead>
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
                colSpan={12}
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
                colSpan={12}
                className="h-24 text-center text-muted-foreground"
              >
                発注中の明細がありません
              </TableCell>
            </TableRow>
          ) : (
            data.items.map((item) => (
              <TableRow key={item.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedIds.includes(item.id)}
                    onCheckedChange={(checked) => handleSelectItem(item.id, !!checked)}
                    aria-label={`${item.product_name}を選択`}
                  />
                </TableCell>
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
  );
}
