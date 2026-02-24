"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatusBadge } from "@/components/common/status-badge";
import { Clock, ArrowRight } from "lucide-react";
import useSWR from "swr";
import { apiClient, getApiBaseUrl } from "@/lib/api/client";
import type {
  OrderStatusHistory as OrderStatusHistoryType,
  OrderStatusHistoryListResponse,
} from "@/types/api";

interface OrderStatusHistoryProps {
  orderId: string;
}

function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const statusLabels: Record<string, string> = {
  ordered: "発注中",
  manufacturing: "製造中",
  delivered: "納入済",
  shipped: "発送完了",
};

function getStatusLabel(status: string): string {
  return statusLabels[status] || status;
}

export function OrderStatusHistory({ orderId }: OrderStatusHistoryProps) {
  const { data, isLoading } = useSWR<OrderStatusHistoryListResponse>(
    `${getApiBaseUrl()}/orders/${orderId}/status-history`,
    (url: string) => apiClient<OrderStatusHistoryListResponse>(`/orders/${orderId}/status-history`)
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          ステータス履歴
        </CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="text-sm text-muted-foreground">読み込み中...</div>
        ) : data && data.items.length > 0 ? (
          <div className="space-y-4">
            {data.items.map((item: OrderStatusHistoryType) => (
              <div
                key={item.id}
                className="flex items-start gap-4 border-l-2 border-muted pl-4 pb-4"
              >
                <div className="flex-1 space-y-1">
                  <div className="text-sm text-muted-foreground">
                    {formatDateTime(item.created_at)}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    {item.from_status ? (
                      <>
                        <StatusBadge status={item.from_status as any} />
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                      </>
                    ) : null}
                    <StatusBadge status={item.to_status as any} />
                  </div>
                  {item.changed_by && (
                    <div className="text-sm text-muted-foreground">
                      {item.changed_by}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-muted-foreground">
            ステータス変更履歴はありません
          </div>
        )}
      </CardContent>
    </Card>
  );
}
