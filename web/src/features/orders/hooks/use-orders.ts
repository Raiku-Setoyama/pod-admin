import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { OrderListResponse, OrderStatus, ShipmentStatus } from "@/types/api";

// 表示用ステータス（Shipmentステータスを含む）
type DisplayStatus = OrderStatus | ShipmentStatus;

interface UseOrdersParams {
  page?: number;
  limit?: number;
  status?: DisplayStatus | null;
  search?: string;
  ordered_from?: string;
  ordered_to?: string;
  shipping_from?: string;
  shipping_to?: string;
}

export function useOrders(params: UseOrdersParams = {}) {
  const {
    page = 1, limit = 20, status, search,
    ordered_from, ordered_to, shipping_from, shipping_to,
  } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (status) queryParams.set("status", status);
  if (search) queryParams.set("search", search);
  if (ordered_from) queryParams.set("ordered_from", ordered_from);
  if (ordered_to) queryParams.set("ordered_to", ordered_to);
  if (shipping_from) queryParams.set("shipping_from", shipping_from);
  if (shipping_to) queryParams.set("shipping_to", shipping_to);

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
