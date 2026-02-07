import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { DashboardSummary } from "@/types/api";

export function useDashboard() {
  const { data, error, isLoading, mutate } = useSWR<DashboardSummary>(
    "/dashboard/summary",
    apiClient,
    {
      refreshInterval: 60000, // Refresh every minute
    }
  );

  return {
    summary: data,
    isLoading,
    error,
    mutate,
  };
}
