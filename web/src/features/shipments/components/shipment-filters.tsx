"use client";

import { format } from "date-fns";
import { ja } from "date-fns/locale";
import { Search, SlidersHorizontal, X } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { DateRangePicker } from "@/components/common/date-range-picker";
import { getShipmentListFilterOptions, getStatusLabel } from "@/constants/status";
import type { ShipmentStatus, PendingOrderStatus } from "@/types/api";

const statusOptions = getShipmentListFilterOptions();

type ShipmentFilterStatus = ShipmentStatus | PendingOrderStatus;

interface ShipmentFiltersProps {
  search: string;
  status: ShipmentFilterStatus | null;
  dateRange?: DateRange;
  estimatedShippingDateRange?: DateRange;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ShipmentFilterStatus | null) => void;
  onDateRangeChange?: (range: DateRange | undefined) => void;
  onEstimatedShippingDateRangeChange?: (range: DateRange | undefined) => void;
  onReset: () => void;
}

function formatDateRange(range: DateRange | undefined): string | null {
  if (!range) return null;
  if (range.from && range.to) {
    return `${format(range.from, "MM/dd", { locale: ja })} - ${format(range.to, "MM/dd", { locale: ja })}`;
  }
  if (range.from) {
    return `${format(range.from, "MM/dd", { locale: ja })} -`;
  }
  return null;
}

export function ShipmentFilters({
  search,
  status,
  dateRange,
  estimatedShippingDateRange,
  onSearchChange,
  onStatusChange,
  onDateRangeChange,
  onEstimatedShippingDateRangeChange,
  onReset,
}: ShipmentFiltersProps) {
  const activeFilterCount =
    (status ? 1 : 0) +
    (dateRange?.from ? 1 : 0) +
    (estimatedShippingDateRange?.from ? 1 : 0);

  const hasActiveFilters = search || activeFilterCount > 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {/* Search box - always visible */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="配送ID、伝票番号、顧客名で検索..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10"
          />
        </div>

        {/* Filter popover button */}
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" className="gap-2">
              <SlidersHorizontal className="h-4 w-4" />
              フィルター
              {activeFilterCount > 0 && (
                <Badge variant="default" className="ml-1 h-5 w-5 p-0 text-xs">
                  {activeFilterCount}
                </Badge>
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-4" align="start">
            <div className="space-y-4">
              <h4 className="font-medium text-sm">フィルター条件</h4>

              {/* Status */}
              <div className="space-y-2">
                <label className="text-sm text-muted-foreground">ステータス</label>
                <Select
                  value={status ?? "all"}
                  onValueChange={(value) =>
                    onStatusChange(value === "all" ? null : (value as ShipmentFilterStatus))
                  }
                >
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="ステータス" />
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

              {/* Created date range */}
              {onDateRangeChange && (
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">作成日</label>
                  <DateRangePicker
                    value={dateRange}
                    onChange={onDateRangeChange}
                    placeholder="作成日を選択"
                    className="w-full"
                  />
                </div>
              )}

              {/* Estimated shipping date range */}
              {onEstimatedShippingDateRangeChange && (
                <div className="space-y-2">
                  <label className="text-sm text-muted-foreground">配送予定日</label>
                  <DateRangePicker
                    value={estimatedShippingDateRange}
                    onChange={onEstimatedShippingDateRangeChange}
                    placeholder="配送予定日を選択"
                    className="w-full"
                  />
                </div>
              )}

              {/* Clear all button */}
              {hasActiveFilters && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full"
                  onClick={onReset}
                >
                  <X className="h-4 w-4 mr-1" />
                  すべてクリア
                </Button>
              )}
            </div>
          </PopoverContent>
        </Popover>
      </div>

      {/* Active filter chips */}
      {activeFilterCount > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {([
            status && { label: `ステータス: ${getStatusLabel(status)}`, onClear: () => onStatusChange(null) },
            dateRange?.from && { label: `作成日: ${formatDateRange(dateRange)}`, onClear: () => onDateRangeChange?.(undefined) },
            estimatedShippingDateRange?.from && { label: `配送予定日: ${formatDateRange(estimatedShippingDateRange)}`, onClear: () => onEstimatedShippingDateRangeChange?.(undefined) },
          ] as const).filter((c): c is { label: string; onClear: () => void } => !!c).map((chip) => (
            <Badge key={chip.label} variant="secondary" className="gap-1 pr-1">
              {chip.label}
              <button
                onClick={chip.onClear}
                className="ml-1 rounded-full p-0.5 hover:bg-muted"
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
