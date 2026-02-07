"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ManufacturerOrderDetail } from "@/features/purchase-orders/components/manufacturer-order-detail";
import { useManufacturerOrderItems } from "@/features/purchase-orders/hooks/use-manufacturer-orders";
import type { ProductType } from "@/types/api";

export default function PurchaseOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const manufacturerId = params.id as string;

  // フィルター状態
  const [orderedFrom, setOrderedFrom] = useState("");
  const [orderedTo, setOrderedTo] = useState("");
  const [productType, setProductType] = useState<ProductType | null>(null);

  const { data, isLoading, isFiltering, error, mutate } = useManufacturerOrderItems(
    manufacturerId,
    {
      orderedFrom: orderedFrom || undefined,
      orderedTo: orderedTo || undefined,
      productType,
    }
  );

  const handleFilterReset = () => {
    setOrderedFrom("");
    setOrderedTo("");
    setProductType(null);
  };

  // 初回ロード時のみ全画面ローディングを表示（dataがない場合）
  if (isLoading && !data) {
    return (
      <PageContainer title="発注詳細" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  if (error || !data) {
    return (
      <PageContainer title="発注詳細" description="エラーが発生しました">
        <div className="text-center py-12">
          <p className="text-muted-foreground">
            発注情報が見つかりません
          </p>
          <Button
            variant="outline"
            onClick={() => router.back()}
            className="mt-4"
          >
            戻る
          </Button>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={`発注詳細: ${data.manufacturer_name}`}
      description={`発注中の受注明細 ${data.total}件`}
      actions={
        <Button
          variant="outline"
          onClick={() => router.push("/purchase-orders")}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          発注一覧に戻る
        </Button>
      }
    >
      <ManufacturerOrderDetail
        data={data}
        isLoading={isFiltering}
        onStatusUpdate={() => mutate()}
        orderedFrom={orderedFrom}
        orderedTo={orderedTo}
        productType={productType}
        onOrderedFromChange={setOrderedFrom}
        onOrderedToChange={setOrderedTo}
        onProductTypeChange={setProductType}
        onFilterReset={handleFilterReset}
      />
    </PageContainer>
  );
}
