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
import type { OrderStatus } from "@/types/api";

const statusOptions: { value: OrderStatus | "all"; label: string }[] = [
  { value: "all", label: "全てのステータス" },
  { value: "ordered", label: "発注済み" },
  { value: "manufacturing", label: "製造中" },
  { value: "delivered", label: "納入済" },
];

interface ManufacturerOrderFiltersProps {
  search: string;
  status: OrderStatus | null;
  onSearchChange: (value: string) => void;
  onStatusChange: (value: OrderStatus | null) => void;
  onReset: () => void;
}

export function ManufacturerOrderFilters({
  search,
  status,
  onSearchChange,
  onStatusChange,
  onReset,
}: ManufacturerOrderFiltersProps) {
  const hasActiveFilters = search || status;

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
