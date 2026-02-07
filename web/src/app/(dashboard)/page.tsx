"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageLoading } from "@/components/common/loading-spinner";
import { SummaryCards } from "@/features/dashboard/components/summary-cards";
import { StatusOverview } from "@/features/dashboard/components/status-overview";
import { useDashboard } from "@/features/dashboard/hooks/use-dashboard";

export default function DashboardPage() {
  const { summary, isLoading } = useDashboard();

  if (isLoading) {
    return (
      <PageContainer title="ダッシュボード" description="受発注・配送の概要">
        <PageLoading />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="ダッシュボード" description="受発注・配送の概要">
      <div className="space-y-6">
        <SummaryCards
          ordersToday={summary?.orders_today ?? 0}
          shipmentsToday={summary?.shipments_today ?? 0}
          orderedCount={summary?.ordered_count ?? 0}
          manufacturingCount={summary?.manufacturing_count ?? 0}
        />

        <div className="grid gap-4 md:grid-cols-2">
          <StatusOverview
            title="受注ステータス"
            statusCounts={summary?.order_status_counts ?? []}
          />
          <StatusOverview
            title="配送ステータス"
            statusCounts={summary?.shipment_status_counts ?? []}
          />
        </div>
      </div>
    </PageContainer>
  );
}
