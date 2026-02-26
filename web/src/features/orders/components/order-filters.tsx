"use client";

import { Search } from "lucide-react";
import { DateRange } from "react-day-picker";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DateRangePicker } from "@/components/common/date-range-picker";
import { getOrderFilterStatusOptions } from "@/constants/status";
import type { OrderStatus, ShipmentStatus } from "@/types/api";

// 表示用ステータス（Shipmentステータスを含む）
type DisplayStatus = OrderStatus | ShipmentStatus;

const statusOptions = getOrderFilterStatusOptions();

interface OrderFiltersProps {
  search: string;
  status: DisplayStatus | null;
  dateRange?: DateRange;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: DisplayStatus | null) => void;
  onDateRangeChange?: (range: DateRange | undefined) => void;
}

export function OrderFilters({
  search,
  status,
  dateRange,
  onSearchChange,
  onStatusChange,
  onDateRangeChange,
}: OrderFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="relative flex-1 min-w-[200px] max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="注文番号、購入者名で検索..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-10"
        />
      </div>

      <Select
        value={status ?? "all"}
        onValueChange={(value) =>
          onStatusChange(value === "all" ? null : (value as DisplayStatus))
        }
      >
        <SelectTrigger className="w-[180px]">
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

      {onDateRangeChange && (
        <DateRangePicker
          value={dateRange}
          onChange={onDateRangeChange}
          placeholder="受注日"
        />
      )}
    </div>
  );
}
