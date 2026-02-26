"use client";

import { X } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { ProductType } from "@/types/api";

const productTypeLabels: Record<ProductType, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  tote_bag: "トートバッグ",
  tshirt: "Tシャツ",
};

const categoryOptions: { value: string; label: string }[] = [
  { value: "all", label: "全ての種類" },
  ...Object.entries(productTypeLabels).map(([value, label]) => ({
    value,
    label,
  })),
];

const statusOptions: { value: string; label: string }[] = [
  { value: "all", label: "全てのステータス" },
  { value: "active", label: "有効" },
  { value: "inactive", label: "無効" },
];

interface ProductFiltersProps {
  category: string | null;
  maker: string | null;
  status: string | null;
  onCategoryChange: (value: string | null) => void;
  onMakerChange: (value: string | null) => void;
  onStatusChange: (value: string | null) => void;
  onReset: () => void;
  manufacturers: Array<{ id: string; name: string }>;
}

export function ProductFilters({
  category,
  maker,
  status,
  onCategoryChange,
  onMakerChange,
  onStatusChange,
  onReset,
  manufacturers,
}: ProductFiltersProps) {
  const hasActiveFilters = category || maker || status;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        {/* Category (種類) select */}
        <Select
          value={category ?? "all"}
          onValueChange={(value) =>
            onCategoryChange(value === "all" ? null : value)
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="全ての種類" />
          </SelectTrigger>
          <SelectContent>
            {categoryOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Manufacturer (メーカー) select */}
        <Select
          value={maker ?? "all"}
          onValueChange={(value) =>
            onMakerChange(value === "all" ? null : value)
          }
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="全てのメーカー" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全てのメーカー</SelectItem>
            {manufacturers.map((mfr) => (
              <SelectItem key={mfr.id} value={mfr.id}>
                {mfr.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Status (ステータス) select */}
        <Select
          value={status ?? "all"}
          onValueChange={(value) =>
            onStatusChange(value === "all" ? null : value)
          }
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="全てのステータス" />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Reset button */}
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <X className="h-4 w-4 mr-1" />
            リセット
          </Button>
        )}
      </div>
    </div>
  );
}
