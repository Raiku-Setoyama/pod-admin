"use client";

import { X } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { ProductType } from "@/types/api";

const productTypeOptions: { value: ProductType | "all"; label: string }[] = [
  { value: "all", label: "全ての商品タイプ" },
  { value: "acrylic_keychain", label: "アクリルキーホルダー" },
  { value: "acrylic_stand", label: "アクリルスタンド" },
  { value: "sticker", label: "ステッカー" },
  { value: "tote_bag", label: "トートバッグ" },
  { value: "mug", label: "マグカップ" },
  { value: "tshirt", label: "Tシャツ" },
];

interface ManufacturerOrderFiltersProps {
  orderedFrom: string;
  orderedTo: string;
  productType: ProductType | null;
  onOrderedFromChange: (value: string) => void;
  onOrderedToChange: (value: string) => void;
  onProductTypeChange: (value: ProductType | null) => void;
  onReset: () => void;
}

export function ManufacturerOrderFilters({
  orderedFrom,
  orderedTo,
  productType,
  onOrderedFromChange,
  onOrderedToChange,
  onProductTypeChange,
  onReset,
}: ManufacturerOrderFiltersProps) {
  const hasActiveFilters = orderedFrom || orderedTo || productType;

  return (
    <div className="flex flex-wrap items-end gap-4 mb-4">
      {/* 受注日時範囲 */}
      <div className="space-y-1">
        <label className="text-sm text-muted-foreground">受注日時</label>
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={orderedFrom}
            onChange={(e) => onOrderedFromChange(e.target.value)}
            className="w-[140px]"
          />
          <span className="text-muted-foreground">~</span>
          <Input
            type="date"
            value={orderedTo}
            onChange={(e) => onOrderedToChange(e.target.value)}
            className="w-[140px]"
          />
        </div>
      </div>

      {/* 商品タイプ */}
      <div className="space-y-1">
        <label className="text-sm text-muted-foreground">商品タイプ</label>
        <Select
          value={productType ?? "all"}
          onValueChange={(value) =>
            onProductTypeChange(value === "all" ? null : (value as ProductType))
          }
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="商品タイプ" />
          </SelectTrigger>
          <SelectContent>
            {productTypeOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* リセットボタン */}
      {hasActiveFilters && (
        <Button variant="ghost" size="sm" onClick={onReset}>
          <X className="h-4 w-4 mr-1" />
          フィルタをリセット
        </Button>
      )}
    </div>
  );
}
