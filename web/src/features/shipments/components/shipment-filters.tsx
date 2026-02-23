"use client";

import { Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { ShipmentStatus } from "@/types/api";

const statusOptions: { value: ShipmentStatus | "all"; label: string }[] = [
  { value: "all", label: "全てのステータス" },
  { value: "pending", label: "配送準備中" },
  { value: "ready", label: "準備完了" },
  { value: "shipped", label: "発送完了" },
];

interface ShipmentFiltersProps {
  // Filter values
  search: string;
  status: ShipmentStatus | null;
  // Handlers
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ShipmentStatus | null) => void;
  onReset: () => void;
}

export function ShipmentFilters({
  search,
  status,
  onSearchChange,
  onStatusChange,
  onReset,
}: ShipmentFiltersProps) {
  const hasActiveFilters = search || status;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-4">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="配送ID、伝票番号、顧客名で検索..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-10"
          />
        </div>

        <Select
          value={status ?? "all"}
          onValueChange={(value) =>
            onStatusChange(value === "all" ? null : (value as ShipmentStatus))
          }
        >
          <SelectTrigger className="w-[160px]">
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

        {/* Reset button */}
        {hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={onReset}>
            <X className="h-4 w-4 mr-1" />
            フィルタをリセット
          </Button>
        )}
      </div>
    </div>
  );
}
