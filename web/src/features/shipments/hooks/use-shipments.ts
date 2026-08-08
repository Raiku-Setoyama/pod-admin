import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ShipmentListWithPendingResponse, ShipmentStatus, ShipmentOrPendingOrder, PendingOrderStatus, ShipmentSortBy, ShipmentSortOrder } from "@/types/api";

type ShipmentFilterStatus = ShipmentStatus | PendingOrderStatus;

interface UseShipmentsParams {
  page?: number;
  limit?: number;
  status?: ShipmentFilterStatus | null;
  search?: string;
  created_from?: string;
  created_to?: string;
  tracking_number?: string;
  carrier?: string;
  shipped_from?: string;
  shipped_to?: string;
  delivered_from?: string;
  delivered_to?: string;
  estimated_shipping_date_from?: string;
  estimated_shipping_date_to?: string;
  sort_by?: ShipmentSortBy;
  sort_order?: ShipmentSortOrder;
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
    estimated_shipping_date_from,
    estimated_shipping_date_to,
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
  if (estimated_shipping_date_from) queryParams.set("estimated_shipping_date_from", estimated_shipping_date_from);
  if (estimated_shipping_date_to) queryParams.set("estimated_shipping_date_to", estimated_shipping_date_to);

  const { data, error, isLoading, mutate } = useSWR<ShipmentListWithPendingResponse>(
    `/shipments?${queryParams.toString()}`,
    apiClient
  );

  return {
    // Return items with unified type (includes both shipments and pending orders)
    items: data?.items ?? [] as ShipmentOrPendingOrder[],
    // Legacy alias for backward compatibility
    shipments: data?.items ?? [] as ShipmentOrPendingOrder[],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    isLoading,
    error,
    mutate,
  };
}
