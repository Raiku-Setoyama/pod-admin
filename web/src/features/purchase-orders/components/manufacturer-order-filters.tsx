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
import { getManufacturerOrderFilterStatusOptions } from "@/constants/status";
import type { OrderStatus } from "@/types/api";

const statusOptions = getManufacturerOrderFilterStatusOptions();

interface ManufacturerOrderFiltersProps {
  search: string;
  status: OrderStatus | null;
  dateRange?: DateRange;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: OrderStatus | null) => void;
  onDateRangeChange?: (range: DateRange | undefined) => void;
  onReset: () => void;
}

export function ManufacturerOrderFilters({
  search,
  status,
  dateRange,
  onSearchChange,
  onStatusChange,
  onDateRangeChange,
  onReset,
}: ManufacturerOrderFiltersProps) {
  const hasActiveFilters = search || status || dateRange?.from;

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
            onStatusChange(value === "all" ? null : (value as OrderStatus))
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

      {/* 日付範囲フィルター */}
      {onDateRangeChange && (
        <DateRangePicker
          value={dateRange}
          onChange={onDateRangeChange}
          placeholder="受注日"
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
