import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type {
  ManufacturerOrderSummaryListResponse,
  ManufacturerOrderItemListResponse,
  OrderStatus,
} from "@/types/api";

export interface ManufacturerOrderFilters {
  status?: OrderStatus | null;
  search?: string;
  ordered_from?: string;
  ordered_to?: string;
}

export function useManufacturerOrderSummary(page = 1, limit = 20) {
  const { data, error, isLoading, mutate } =
    useSWR<ManufacturerOrderSummaryListResponse>(
      `/manufacturers/order-summary?page=${page}&limit=${limit}`,
      apiClient
    );

  return {
    manufacturers: data?.items ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    isLoading,
    error,
    mutate,
  };
}

export function useManufacturerOrderItems(
  manufacturerId: string | null,
  filters?: ManufacturerOrderFilters
) {
  // クエリパラメータ構築
  const queryParams = new URLSearchParams();
  if (filters?.status) queryParams.set("status", filters.status);
  if (filters?.search) queryParams.set("search", filters.search);
  if (filters?.ordered_from) queryParams.set("ordered_from", filters.ordered_from);
  if (filters?.ordered_to) queryParams.set("ordered_to", filters.ordered_to);

  const queryString = queryParams.toString();
  const url = manufacturerId
    ? `/manufacturers/${manufacturerId}/order-items${queryString ? `?${queryString}` : ""}`
    : null;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<ManufacturerOrderItemListResponse>(url, apiClient, {
      keepPreviousData: true,
    });

  return {
    data,
    isLoading,
    // フィルター変更中はisValidatingがtrueになる（データ再取得中）
    isFiltering: isValidating && !isLoading,
    error,
    mutate,
  };
}
