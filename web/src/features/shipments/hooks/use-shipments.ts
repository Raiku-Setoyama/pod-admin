import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ShipmentListResponse, ShipmentStatus } from "@/types/api";

type SortBy = "created_at" | "shipped_at" | "delivered_at";
type SortOrder = "asc" | "desc";

interface UseShipmentsParams {
  page?: number;
  limit?: number;
  status?: ShipmentStatus | null;
  search?: string;
  created_from?: string;
  created_to?: string;
  tracking_number?: string;
  carrier?: string;
  shipped_from?: string;
  shipped_to?: string;
  delivered_from?: string;
  delivered_to?: string;
  sort_by?: SortBy;
  sort_order?: SortOrder;
}

export function useShipments(params: UseShipmentsParams = {}) {
  const {
    page = 1,
    limit = 20,
    status,
    search,
    created_from,
    created_to,
    tracking_number,
    carrier,
    shipped_from,
    shipped_to,
    delivered_from,
    delivered_to,
    sort_by = "created_at",
    sort_order = "desc",
  } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  queryParams.set("sort_by", sort_by);
  queryParams.set("sort_order", sort_order);
  if (status) queryParams.set("status", status);
  if (search) queryParams.set("search", search);
  if (created_from) queryParams.set("created_from", created_from);
  if (created_to) queryParams.set("created_to", created_to);
  if (tracking_number) queryParams.set("tracking_number", tracking_number);
  if (carrier) queryParams.set("carrier", carrier);
  if (shipped_from) queryParams.set("shipped_from", shipped_from);
  if (shipped_to) queryParams.set("shipped_to", shipped_to);
  if (delivered_from) queryParams.set("delivered_from", delivered_from);
  if (delivered_to) queryParams.set("delivered_to", delivered_to);

  const { data, error, isLoading, mutate } = useSWR<ShipmentListResponse>(
    `/shipments?${queryParams.toString()}`,
    apiClient
  );

  return {
    shipments: data?.items ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    isLoading,
    error,
    mutate,
  };
}
