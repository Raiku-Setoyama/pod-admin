import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  MANUFACTURING_DATA_STATUS_COLORS,
  MANUFACTURING_DATA_STATUS_LABELS,
} from "@/constants/status";
import type { ManufacturingDataStatus } from "@/types/api";

interface ManufacturingDataBadgeProps {
  status: ManufacturingDataStatus;
  className?: string;
}

/**
 * 製造データ生成ステータス（v2）のバッジ。
 * 配送ステータスと値が重複するため共通 StatusBadge とは別コンポーネントとする。
 */
export function ManufacturingDataBadge({ status, className }: ManufacturingDataBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn("border font-medium", MANUFACTURING_DATA_STATUS_COLORS[status], className)}
    >
      {MANUFACTURING_DATA_STATUS_LABELS[status]}
    </Badge>
  );
}
