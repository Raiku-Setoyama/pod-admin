import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// Order status (受注ステータス)
type OrderStatus =
  | "ordered"
  | "manufacturing"
  | "delivered"
  | "shipped";

// Shipment status (配送ステータス)
type ShipmentStatus = "pending" | "ready" | "shipped";

type StatusType = OrderStatus | ShipmentStatus;

const statusConfig: Record<
  StatusType,
  { label: string; variant: "default" | "secondary" | "destructive" | "outline" }
> = {
  pending: { label: "配送準備中", variant: "outline" },
  ordered: { label: "発注中", variant: "default" },
  manufacturing: { label: "製造中", variant: "secondary" },
  delivered: { label: "納入済", variant: "default" },
  shipped: { label: "発送完了", variant: "default" },
  ready: { label: "準備完了", variant: "secondary" },
};

const statusColors: Record<StatusType, string> = {
  pending: "bg-gray-100 text-gray-700 border-gray-300",
  ordered: "bg-yellow-100 text-yellow-700 border-yellow-300",
  manufacturing: "bg-blue-100 text-blue-700 border-blue-300",
  delivered: "bg-purple-100 text-purple-700 border-purple-300",
  shipped: "bg-emerald-100 text-emerald-700 border-emerald-300",
  ready: "bg-cyan-100 text-cyan-700 border-cyan-300",
};

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const config = statusConfig[status];

  if (!config) {
    return (
      <Badge variant="outline" className={className}>
        {status}
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={cn(
        "border font-medium",
        statusColors[status],
        className
      )}
    >
      {config.label}
    </Badge>
  );
}
