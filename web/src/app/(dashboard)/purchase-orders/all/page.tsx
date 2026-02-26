"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { AllManufacturerOrderList } from "@/features/purchase-orders/components/all-manufacturer-order-list";
import { AllManufacturerOrderFilters } from "@/features/purchase-orders/components/all-manufacturer-order-filters";
import { useAllManufacturerOrderItems } from "@/features/purchase-orders/hooks/use-manufacturer-orders";
import { useManufacturers } from "@/features/manufacturers/hooks/use-manufacturers";

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

export default function AllPurchaseOrdersPage() {
  const router = useRouter();

  // フィルター状態
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [manufacturerId, setManufacturerId] = useState<string | null>(null);
  const [productType, setProductType] = useState<string | null>(null);
  const [orderedFrom, setOrderedFrom] = useState("");
  const [orderedTo, setOrderedTo] = useState("");

  // デバウンスされた検索値（300ms）
  const debouncedSearch = useDebounce(search, 300);

  // メーカー一覧取得（フィルター用）
  const { manufacturers } = useManufacturers({ limit: 100 });

  const { data, isLoading, isFiltering } = useAllManufacturerOrderItems({
    search: debouncedSearch || undefined,
    status: status || undefined,
    manufacturer_id: manufacturerId || undefined,
    product_type: productType || undefined,
    ordered_from: orderedFrom || undefined,
    ordered_to: orderedTo || undefined,
  });

  const handleFilterReset = () => {
    setSearch("");
    setStatus(null);
    setManufacturerId(null);
    setProductType(null);
    setOrderedFrom("");
    setOrderedTo("");
  };

  // メーカー一覧をフィルターコンポーネント用に変換
  const manufacturerOptions = manufacturers.map((m) => ({
    id: m.id,
    name: m.name,
  }));

  // 初回ロード時のみ全画面ローディングを表示
  if (isLoading && !data) {
    return (
      <PageContainer title="すべての発注" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  const displayData = data ?? {
    items: [],
    total: 0,
    total_quantity: 0,
  };

  return (
    <PageContainer
      title="すべての発注"
      description="全メーカーの発注明細を横断的に表示"
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
      <div className="space-y-4">
        <AllManufacturerOrderFilters
          search={search}
          status={status}
          manufacturerId={manufacturerId}
          productType={productType}
          orderedFrom={orderedFrom}
          orderedTo={orderedTo}
          onSearchChange={setSearch}
          onStatusChange={setStatus}
          onManufacturerIdChange={setManufacturerId}
          onProductTypeChange={setProductType}
          onOrderedFromChange={setOrderedFrom}
          onOrderedToChange={setOrderedTo}
          onReset={handleFilterReset}
          manufacturers={manufacturerOptions}
        />

        <AllManufacturerOrderList
          data={displayData}
          isLoading={isFiltering}
        />
      </div>
    </PageContainer>
  );
}
