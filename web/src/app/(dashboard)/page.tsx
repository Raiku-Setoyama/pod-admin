"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import { DateRange } from "react-day-picker";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { SummaryCards } from "@/features/dashboard/components/summary-cards";
import { useDashboard } from "@/features/dashboard/hooks/use-dashboard";
import { OrderFilters } from "@/features/orders/components/order-filters";
import { OrderList } from "@/features/orders/components/order-list";
import { useOrders } from "@/features/orders/hooks/use-orders";
import type { Order, OrderStatus, ShipmentStatus } from "@/types/api";

// 表示用ステータス（Shipmentステータスを含む）
type DisplayStatus = OrderStatus | ShipmentStatus;

export default function DashboardPage() {
  const router = useRouter();
  const { summary, isLoading: isDashboardLoading } = useDashboard();

  // Orders state
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<DisplayStatus | null>(null);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);

  const { orders, total, isLoading: isOrdersLoading } = useOrders({
    page,
    limit,
    search,
    status,
    ordered_from: dateRange?.from ? format(dateRange.from, "yyyy-MM-dd") : undefined,
    ordered_to: dateRange?.to ? format(dateRange.to, "yyyy-MM-dd") : undefined,
  });

  // 発送待ち件数の計算（pending + ready）
  const pendingShipmentCount = summary?.shipment_status_counts
    ?.filter(s => ["pending", "ready"].includes(s.status))
    ?.reduce((sum, s) => sum + s.count, 0) ?? 0;

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

  if (isDashboardLoading) {
    return (
      <PageContainer title="受注管理" description="受注・発注・配送の概要">
        <PageLoading />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="受注管理" description="受注・発注・配送の概要">
      <div className="space-y-6">
        <SummaryCards
          ordersToday={summary?.orders_today ?? 0}
          orderedCount={summary?.ordered_count ?? 0}
          manufacturingCount={summary?.manufacturing_count ?? 0}
          pendingShipmentCount={pendingShipmentCount}
        />

        <div className="space-y-4">
          <OrderFilters
            search={search}
            status={status}
            dateRange={dateRange}
            onSearchChange={(value) => { setSearch(value); setPage(1); }}
            onStatusChange={(value) => { setStatus(value); setPage(1); }}
            onDateRangeChange={(range) => { setDateRange(range); setPage(1); }}
          />

          {isOrdersLoading ? (
            <PageLoading />
          ) : (
            <>
              <OrderList
                orders={orders}
                onRowClick={handleRowClick}
              />
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
      </div>
    </PageContainer>
  );
}
