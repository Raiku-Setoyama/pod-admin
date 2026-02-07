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

const carrierOptions = [
  { value: "all", label: "全ての運送会社" },
  { value: "yamato", label: "ヤマト運輸" },
  { value: "sagawa", label: "佐川急便" },
  { value: "japanpost", label: "日本郵便" },
];

type SortBy = "created_at" | "shipped_at" | "delivered_at";
type SortOrder = "asc" | "desc";

const sortOptions: { value: `${SortBy}_${SortOrder}`; label: string }[] = [
  { value: "created_at_desc", label: "作成日時 (新しい順)" },
  { value: "created_at_asc", label: "作成日時 (古い順)" },
  { value: "shipped_at_desc", label: "発送日時 (新しい順)" },
  { value: "shipped_at_asc", label: "発送日時 (古い順)" },
  { value: "delivered_at_desc", label: "配送完了予定日時 (新しい順)" },
  { value: "delivered_at_asc", label: "配送完了予定日時 (古い順)" },
];

interface ShipmentFiltersProps {
  // Filter values
  search: string;
  status: ShipmentStatus | null;
  trackingNumber: string;
  carrier: string | null;
  shippedFrom: string;
  shippedTo: string;
  createdFrom: string;
  createdTo: string;
  deliveredFrom: string;
  deliveredTo: string;
  sortBy: SortBy;
  sortOrder: SortOrder;
  // Handlers
  onSearchChange: (value: string) => void;
  onStatusChange: (value: ShipmentStatus | null) => void;
  onTrackingNumberChange: (value: string) => void;
  onCarrierChange: (value: string | null) => void;
  onShippedFromChange: (value: string) => void;
  onShippedToChange: (value: string) => void;
  onCreatedFromChange: (value: string) => void;
  onCreatedToChange: (value: string) => void;
  onDeliveredFromChange: (value: string) => void;
  onDeliveredToChange: (value: string) => void;
  onSortChange: (sortBy: SortBy, sortOrder: SortOrder) => void;
  onReset: () => void;
}

export function ShipmentFilters({
  search,
  status,
  trackingNumber,
  carrier,
  shippedFrom,
  shippedTo,
  createdFrom,
  createdTo,
  deliveredFrom,
  deliveredTo,
  sortBy,
  sortOrder,
  onSearchChange,
  onStatusChange,
  onTrackingNumberChange,
  onCarrierChange,
  onShippedFromChange,
  onShippedToChange,
  onCreatedFromChange,
  onCreatedToChange,
  onDeliveredFromChange,
  onDeliveredToChange,
  onSortChange,
  onReset,
}: ShipmentFiltersProps) {
  const hasActiveFilters =
    search ||
    status ||
    trackingNumber ||
    carrier ||
    shippedFrom ||
    shippedTo ||
    createdFrom ||
    createdTo ||
    deliveredFrom ||
    deliveredTo;

  const handleSortChange = (value: string) => {
    const [by, order] = value.split("_") as [SortBy, SortOrder];
    // Handle special case for created_at which has underscore
    if (value.startsWith("created_at_")) {
      onSortChange("created_at", value.endsWith("asc") ? "asc" : "desc");
    } else if (value.startsWith("shipped_at_")) {
      onSortChange("shipped_at", value.endsWith("asc") ? "asc" : "desc");
    } else if (value.startsWith("delivered_at_")) {
      onSortChange("delivered_at", value.endsWith("asc") ? "asc" : "desc");
    }
  };

  return (
    <div className="space-y-4">
      {/* Row 1: Search, Status, Carrier, Sort */}
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

        <Select
          value={carrier ?? "all"}
          onValueChange={(value) =>
            onCarrierChange(value === "all" ? null : value)
          }
        >
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="運送会社" />
          </SelectTrigger>
          <SelectContent>
            {carrierOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={`${sortBy}_${sortOrder}`}
          onValueChange={handleSortChange}
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="並び替え" />
          </SelectTrigger>
          <SelectContent>
            {sortOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Row 2: Tracking Number */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[200px] max-w-xs">
          <Input
            placeholder="伝票番号"
            value={trackingNumber}
            onChange={(e) => onTrackingNumberChange(e.target.value)}
          />
        </div>
      </div>

      {/* Row 3: Date filters */}
      <div className="flex flex-wrap items-end gap-4">
        {/* Created date range */}
        <div className="space-y-1">
          <label className="text-sm text-muted-foreground">作成日時</label>
          <div className="flex items-center gap-2">
            <Input
              type="date"
              value={createdFrom}
              onChange={(e) => onCreatedFromChange(e.target.value)}
              className="w-[140px]"
            />
            <span className="text-muted-foreground">~</span>
            <Input
              type="date"
              value={createdTo}
              onChange={(e) => onCreatedToChange(e.target.value)}
              className="w-[140px]"
            />
          </div>
        </div>

        {/* Shipped date range */}
        <div className="space-y-1">
          <label className="text-sm text-muted-foreground">発送日時</label>
          <div className="flex items-center gap-2">
            <Input
              type="date"
              value={shippedFrom}
              onChange={(e) => onShippedFromChange(e.target.value)}
              className="w-[140px]"
            />
            <span className="text-muted-foreground">~</span>
            <Input
              type="date"
              value={shippedTo}
              onChange={(e) => onShippedToChange(e.target.value)}
              className="w-[140px]"
            />
          </div>
        </div>

        {/* Delivered date range */}
        <div className="space-y-1">
          <label className="text-sm text-muted-foreground">配送完了予定日時</label>
          <div className="flex items-center gap-2">
            <Input
              type="date"
              value={deliveredFrom}
              onChange={(e) => onDeliveredFromChange(e.target.value)}
              className="w-[140px]"
            />
            <span className="text-muted-foreground">~</span>
            <Input
              type="date"
              value={deliveredTo}
              onChange={(e) => onDeliveredToChange(e.target.value)}
              className="w-[140px]"
            />
          </div>
        </div>

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
