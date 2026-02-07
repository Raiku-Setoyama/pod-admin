import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type {
  ManufacturerOrderSummaryListResponse,
  ManufacturerOrderItemListResponse,
} from "@/types/api";

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

export function useManufacturerOrderItems(manufacturerId: string | null) {
  const { data, error, isLoading, mutate } =
    useSWR<ManufacturerOrderItemListResponse>(
      manufacturerId ? `/manufacturers/${manufacturerId}/order-items` : null,
      apiClient
    );

  return {
    data,
    isLoading,
    error,
    mutate,
  };
}
