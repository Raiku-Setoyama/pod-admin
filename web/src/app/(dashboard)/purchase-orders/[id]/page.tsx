"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { format } from "date-fns";
import { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ManufacturerOrderDetail } from "@/features/purchase-orders/components/manufacturer-order-detail";
import { useManufacturerOrderItems } from "@/features/purchase-orders/hooks/use-manufacturer-orders";
import type { OrderStatus } from "@/types/api";

// デバウンスフック
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

export default function PurchaseOrderDetailPage() {
  const params = useParams();
  const router = useRouter();
  const manufacturerId = params.id as string;

  // フィルター状態（新しい形式）
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<OrderStatus | null>(null);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const [expectedDeliveryRange, setExpectedDeliveryRange] = useState<DateRange | undefined>(undefined);

  // デバウンスされた検索値（300ms）
  const debouncedSearch = useDebounce(search, 300);

  const { data, isLoading, isFiltering, error, mutate } = useManufacturerOrderItems(
    manufacturerId,
    {
      search: debouncedSearch || undefined,
      status,
      ordered_from: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
      ordered_to: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
      expected_delivery_from: expectedDeliveryRange?.from ? format(expectedDeliveryRange.from, "yyyy-MM-dd") : undefined,
      expected_delivery_to: expectedDeliveryRange?.to ? format(expectedDeliveryRange.to, "yyyy-MM-dd") : undefined,
    }
  );

  const handleFilterReset = () => {
    setSearch("");
    setStatus(null);
    setDateRange(undefined);
    setExpectedDeliveryRange(undefined);
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
        search={search}
        status={status}
        dateRange={dateRange}
        expectedDeliveryRange={expectedDeliveryRange}
        onSearchChange={setSearch}
        onStatusChange={setStatus}
        onDateRangeChange={setDateRange}
        onExpectedDeliveryRangeChange={setExpectedDeliveryRange}
        onFilterReset={handleFilterReset}
      />
    </PageContainer>
  );
}
