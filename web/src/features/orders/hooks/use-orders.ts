import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { OrderListResponse, OrderStatus } from "@/types/api";

interface UseOrdersParams {
  page?: number;
  limit?: number;
  status?: OrderStatus | null;
  search?: string;
  ordered_from?: string;
  ordered_to?: string;
}

export function useOrders(params: UseOrdersParams = {}) {
  const { page = 1, limit = 20, status, search, ordered_from, ordered_to } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (status) queryParams.set("status", status);
  if (search) queryParams.set("search", search);
  if (ordered_from) queryParams.set("ordered_from", ordered_from);
  if (ordered_to) queryParams.set("ordered_to", ordered_to);

  const { data, error, isLoading, mutate } = useSWR<OrderListResponse>(
    `/orders?${queryParams.toString()}`,
    apiClient
  );

  return {
    orders: data?.items ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    isLoading,
    error,
    mutate,
  };
}
