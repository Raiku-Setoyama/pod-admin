"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { OrderDetail } from "@/features/orders/components/order-detail";
import { apiClient } from "@/lib/api/client";
import type { Order } from "@/types/api";

const fetcher = (url: string) => apiClient<Order>(url);

export default function OrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const orderId = params.id as string;

  const { data: order, isLoading, error, mutate } = useSWR<Order>(
    `/orders/${orderId}`,
    fetcher,
    {
      // 製造データ生成中（pending/generating）は完成までポーリングする
      refreshInterval: (latest?: Order) =>
        latest?.items?.some(
          (item) =>
            item.manufacturing_data &&
            (item.manufacturing_data.status === "pending" ||
              item.manufacturing_data.status === "generating")
        )
          ? 5000
          : 0,
    }
  );

  if (isLoading) {
    return (
      <PageContainer title="受注詳細" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  if (error || !order) {
    return (
      <PageContainer title="受注詳細" description="エラーが発生しました">
        <div className="text-center py-12">
          <p className="text-muted-foreground">受注が見つかりません</p>
          <Button variant="outline" onClick={() => router.back()} className="mt-4">
            戻る
          </Button>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={`受注詳細: ${order.order_number}`}
      description={`${order.source ?? '不明'} - ${order.customer_name}`}
      actions={
        <Button variant="outline" onClick={() => router.push("/orders")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          受注一覧に戻る
        </Button>
      }
    >
      <OrderDetail order={order} onRefresh={() => mutate()} />
    </PageContainer>
  );
}
