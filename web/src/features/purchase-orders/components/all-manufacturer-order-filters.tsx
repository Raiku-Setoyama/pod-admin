"use client";

import { X } from "lucide-react";
import { DateRange } from "react-day-picker";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { DateRangePicker } from "@/components/common/date-range-picker";
import type { OrderStatus } from "@/types/api";

const statusOptions: { value: OrderStatus | "all"; label: string }[] = [
  { value: "all", label: "全てのステータス" },
  { value: "ordered", label: "発注済み" },
  { value: "manufacturing", label: "製造中" },
  { value: "delivered", label: "納入済" },
];

interface ManufacturerOption {
  id: string;
  name: string;
}

interface AllManufacturerOrderFiltersProps {
  search: string;
  status: string | null;
  manufacturerId: string | null;
  productType: string | null;
  orderedFrom: string;
  orderedTo: string;
  expectedDeliveryRange?: DateRange;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: string | null) => void;
  onManufacturerIdChange: (value: string | null) => void;
  onProductTypeChange: (value: string | null) => void;
  onOrderedFromChange: (value: string) => void;
  onOrderedToChange: (value: string) => void;
  onExpectedDeliveryRangeChange?: (range: DateRange | undefined) => void;
  onReset: () => void;
  manufacturers: ManufacturerOption[];
}

export function AllManufacturerOrderFilters({
  search,
  status,
  manufacturerId,
  productType,
  orderedFrom,
  orderedTo,
  expectedDeliveryRange,
  onSearchChange,
  onStatusChange,
  onManufacturerIdChange,
  onProductTypeChange,
  onOrderedFromChange,
  onOrderedToChange,
  onExpectedDeliveryRangeChange,
  onReset,
  manufacturers,
}: AllManufacturerOrderFiltersProps) {
  const hasActiveFilters = search || status || manufacturerId || productType || orderedFrom || orderedTo || expectedDeliveryRange?.from;

  return (
    <div className="flex flex-wrap items-end gap-4 mb-4">
      {/* キーワード検索 */}
      <div className="space-y-1">
        <Input
          type="text"
          placeholder="注文番号、製品番号、商品名で検索..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-[280px]"
        />
      </div>

      {/* ステータスフィルター */}
      <div className="space-y-1">
        <Select
          value={status ?? "all"}
          onValueChange={(value) =>
            onStatusChange(value === "all" ? null : value)
          }
        >
          <SelectTrigger className="w-[180px]">
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
      </div>

      {/* メーカーフィルター */}
      <div className="space-y-1">
        <Select
          value={manufacturerId ?? "all"}
          onValueChange={(value) =>
            onManufacturerIdChange(value === "all" ? null : value)
          }
        >
          <SelectTrigger className="w-[200px]">
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
      </div>

      {/* 納品予定日フィルター */}
      {onExpectedDeliveryRangeChange && (
        <DateRangePicker
          value={expectedDeliveryRange}
          onChange={onExpectedDeliveryRangeChange}
          placeholder="納品予定日"
        />
      )}

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
