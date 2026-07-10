import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import { isManufacturingDataActive } from "@/constants/status";
import type {
  ManufacturerOrderSummaryListResponse,
  ManufacturerOrderItemListResponse,
  AllManufacturerOrderItemListResponse,
  OrderStatus,
} from "@/types/api";

export interface ManufacturerOrderFilters {
  status?: OrderStatus | null;
  search?: string;
  ordered_from?: string;
  ordered_to?: string;
  expected_delivery_from?: string;
  expected_delivery_to?: string;
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
  if (filters?.expected_delivery_from) queryParams.set("expected_delivery_from", filters.expected_delivery_from);
  if (filters?.expected_delivery_to) queryParams.set("expected_delivery_to", filters.expected_delivery_to);

  const queryString = queryParams.toString();
  const url = manufacturerId
    ? `/manufacturers/${manufacturerId}/order-items${queryString ? `?${queryString}` : ""}`
    : null;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<ManufacturerOrderItemListResponse>(url, apiClient, {
      keepPreviousData: true,
      // 製造データ生成中（pending/generating）の明細がある間はポーリングする。
      // 発注可否ゲート（未ready=選択不可）を持つ画面なので、生成完了を検知して
      // 自動的に選択可能へ更新する（手動リロード不要）。
      refreshInterval: (latest?: ManufacturerOrderItemListResponse) =>
        latest?.items?.some((item) =>
          isManufacturingDataActive(item.manufacturing_status)
        )
          ? 5000
          : 0,
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

export interface AllManufacturerOrderFiltersParams {
  status?: string | null;
  search?: string;
  manufacturer_id?: string | null;
  product_type?: string | null;
  ordered_from?: string;
  ordered_to?: string;
  expected_delivery_from?: string;
  expected_delivery_to?: string;
}

export function useAllManufacturerOrderItems(
  filters?: AllManufacturerOrderFiltersParams
) {
  // クエリパラメータ構築
  const queryParams = new URLSearchParams();
  if (filters?.status) queryParams.set("status", filters.status);
  if (filters?.search) queryParams.set("search", filters.search);
  if (filters?.manufacturer_id) queryParams.set("manufacturer_id", filters.manufacturer_id);
  if (filters?.product_type) queryParams.set("product_type", filters.product_type);
  if (filters?.ordered_from) queryParams.set("ordered_from", filters.ordered_from);
  if (filters?.ordered_to) queryParams.set("ordered_to", filters.ordered_to);
  if (filters?.expected_delivery_from) queryParams.set("expected_delivery_from", filters.expected_delivery_from);
  if (filters?.expected_delivery_to) queryParams.set("expected_delivery_to", filters.expected_delivery_to);

  const queryString = queryParams.toString();
  const url = `/manufacturers/all-order-items${queryString ? `?${queryString}` : ""}`;

  const { data, error, isLoading, isValidating, mutate } =
    useSWR<AllManufacturerOrderItemListResponse>(url, apiClient, {
      keepPreviousData: true,
    });

  return {
    data,
    isLoading,
    isFiltering: isValidating && !isLoading,
    error,
    mutate,
  };
}
