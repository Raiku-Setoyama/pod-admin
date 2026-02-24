import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { OrderSourceListResponse } from "@/types/api";

interface UseOrderSourcesParams {
  page?: number;
  limit?: number;
  is_active?: boolean;
}

export function useOrderSources(params: UseOrderSourcesParams = {}) {
  const { page = 1, limit = 20, is_active } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (is_active !== undefined) queryParams.set("is_active", String(is_active));

  const { data, error, isLoading, mutate } = useSWR<OrderSourceListResponse>(
    `/order-sources?${queryParams.toString()}`,
    apiClient
  );

  return {
    orderSources: data?.items ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    isLoading,
    error,
    mutate,
  };
}
