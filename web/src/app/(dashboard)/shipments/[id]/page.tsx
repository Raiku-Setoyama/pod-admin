"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ShipmentDetail } from "@/features/shipments/components/shipment-detail";
import { apiClient } from "@/lib/api/client";
import type { Shipment } from "@/types/api";

const fetcher = (url: string) => apiClient<Shipment>(url);

export default function ShipmentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const shipmentId = params.id as string;

  const { data: shipment, isLoading, error, mutate } = useSWR<Shipment>(
    `/shipments/${shipmentId}`,
    fetcher
  );

  if (isLoading) {
    return (
      <PageContainer title="配送詳細" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  if (error || !shipment) {
    return (
      <PageContainer title="配送詳細" description="エラーが発生しました">
        <div className="text-center py-12">
          <p className="text-muted-foreground">配送が見つかりません</p>
          <Button variant="outline" onClick={() => router.back()} className="mt-4">
            戻る
          </Button>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={`配送詳細: ${shipment.id.slice(0, 8)}`}
      description={`${shipment.customer_name} - ${shipment.items.length}件の商品`}
      actions={
        <Button variant="outline" onClick={() => router.push("/shipments")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          配送一覧に戻る
        </Button>
      }
    >
      <ShipmentDetail shipment={shipment} onUpdate={mutate} />
    </PageContainer>
  );
}
