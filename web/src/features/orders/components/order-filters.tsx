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
import type { OrderStatus } from "@/types/api";

const statusOptions: { value: OrderStatus | "all"; label: string }[] = [
  { value: "all", label: "全てのステータス" },
  { value: "ordered", label: "発注中" },
  { value: "manufacturing", label: "製造中" },
  { value: "delivered", label: "納入済" },
  { value: "shipped", label: "発送完了" },
];

interface OrderFiltersProps {
  search: string;
  status: OrderStatus | null;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: OrderStatus | null) => void;
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
          onStatusChange(value === "all" ? null : (value as OrderStatus))
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
