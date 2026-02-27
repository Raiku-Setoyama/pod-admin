"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { ManufacturerOrderList } from "@/features/purchase-orders/components/manufacturer-order-list";
import { useManufacturerOrderSummary } from "@/features/purchase-orders/hooks/use-manufacturer-orders";
import type { ManufacturerOrderSummary } from "@/types/api";

export default function PurchaseOrdersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  const { manufacturers, total, isLoading } = useManufacturerOrderSummary(
    page,
    limit
  );

  const handleRowClick = (manufacturer: ManufacturerOrderSummary) => {
    router.push(`/purchase-orders/${manufacturer.id}`);
  };

  return (
    <PageContainer
      title="発注一覧"
      description="発注中の商品をメーカー別に表示"
      actions={
        <Button
          variant="outline"
          onClick={() => router.push("/purchase-orders/all")}
        >
          <List className="h-4 w-4 mr-2" />
          すべての発注
        </Button>
      }
    >
      <div className="space-y-4">
        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ManufacturerOrderList
              manufacturers={manufacturers}
              onRowClick={handleRowClick}
            />
            {total > limit && (
              <Pagination
                page={page}
                limit={limit}
                total={total}
                onPageChange={setPage}
                onLimitChange={(newLimit) => {
                  setLimit(newLimit);
                  setPage(1);
                }}
              />
            )}
          </>
        )}
      </div>
    </PageContainer>
  );
}
