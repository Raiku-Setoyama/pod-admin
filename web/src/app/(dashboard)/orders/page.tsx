"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { OrderFilters } from "@/features/orders/components/order-filters";
import { OrderList } from "@/features/orders/components/order-list";
import { useOrders } from "@/features/orders/hooks/use-orders";
import type { Order, OrderStatus } from "@/types/api";

export default function OrdersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<OrderStatus | null>(null);

  const { orders, total, isLoading } = useOrders({
    page,
    limit,
    search,
    status,
  });

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleLimitChange = (newLimit: number) => {
    setLimit(newLimit);
    setPage(1);
  };

  const handleRowClick = (order: Order) => {
    router.push(`/orders/${order.id}`);
  };

  return (
    <PageContainer
      title="受注一覧"
      description="外部販売サイトからの受注情報"
    >
      <div className="space-y-4">
        <OrderFilters
          search={search}
          status={status}
          onSearchChange={setSearch}
          onStatusChange={setStatus}
        />

        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <OrderList orders={orders} onRowClick={handleRowClick} />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={handlePageChange}
              onLimitChange={handleLimitChange}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
