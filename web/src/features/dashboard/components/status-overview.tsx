import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/common/status-badge";
import type { StatusCount } from "@/types/api";

interface StatusOverviewProps {
  title: string;
  statusCounts: StatusCount[];
}

export function StatusOverview({ title, statusCounts }: StatusOverviewProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {statusCounts.length === 0 ? (
            <p className="text-sm text-muted-foreground">データがありません</p>
          ) : (
            statusCounts.map((item) => (
              <div
                key={item.status}
                className="flex items-center justify-between"
              >
                <StatusBadge
                  status={item.status as never}
                />
                <span className="text-sm font-medium">{item.count}件</span>
              </div>
            ))
          )}
        </div>
      </CardContent>
    </Card>
  );
}
