import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  STATUS_LABELS,
  STATUS_COLORS,
  type StatusType,
} from "@/constants/status";

interface StatusBadgeProps {
  status: StatusType;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const label = STATUS_LABELS[status];
  const colorClass = STATUS_COLORS[status];

  if (!label) {
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
        colorClass,
        className
      )}
    >
      {label}
    </Badge>
  );
}
