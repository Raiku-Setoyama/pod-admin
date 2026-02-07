"use client";

import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { OrderStatus, ShipmentStatus } from "@/types/api";

// 表示用ステータス（Shipmentステータスを含む）
type DisplayStatus = OrderStatus | ShipmentStatus;

const statusOptions: { value: DisplayStatus | "all"; label: string }[] = [
  { value: "all", label: "全てのステータス" },
  { value: "ordered", label: "発注中" },
  { value: "manufacturing", label: "製造中" },
  { value: "pending", label: "配送準備中" },
  { value: "ready", label: "準備完了" },
  { value: "shipped", label: "発送完了" },
];

interface OrderFiltersProps {
  search: string;
  status: DisplayStatus | null;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: DisplayStatus | null) => void;
}

export function OrderFilters({
  search,
  status,
  onSearchChange,
  onStatusChange,
}: OrderFiltersProps) {
  return (
    <div className="flex items-center gap-4">
      <div className="relative flex-1 max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="受注ID、購入者名で検索..."
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
    </div>
  );
}
