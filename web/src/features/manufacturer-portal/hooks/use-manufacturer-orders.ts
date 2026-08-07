import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import { useLocalStorageValue } from "@/lib/use-local-storage-value";
import type { OrderItemStatus } from "@/types/api";

// 発注アイテム（受注明細）
export interface ManufacturerOrderItem {
  id: string;
  order_id: string;
  order_number: string;
  uid: string | null;
  product_id: string;
  product_name: string;
  product_type: string;
  price: number;
  quantity: number;
  size: string | null;
  position: string | null;
  color: string | null;
  design_image_url: string | null;
  thumbnail_image_url: string | null;
  ordered_at: string;
  customer_name: string;
  status: OrderItemStatus;
  lead_time_days: number;
  expected_delivery_date: string;
}

// 発注アイテム一覧レスポンス
export interface ManufacturerOrderItemsResponse {
  manufacturer_id: string;
  manufacturer_name: string;
  items: ManufacturerOrderItem[];
  total: number;
  total_quantity: number;
  total_amount: number;
}

export interface ManufacturerOrderFilters {
  search?: string;
  status?: string | null;
}

const fetcher = async (url: string) => {
  const token = localStorage.getItem("manufacturer_token");
  if (!token) {
    throw new Error("No authentication token");
  }
  return apiClient<ManufacturerOrderItemsResponse>(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
};

export function useManufacturerOrderItems(filters?: ManufacturerOrderFilters) {
  // localStorage は React の外側の store。購読して SWR キーを更新させる。
  const token = useLocalStorageValue("manufacturer_token");

  // クエリパラメータ構築
  const queryParams = new URLSearchParams();
  if (filters?.search) queryParams.set("search", filters.search);
  if (filters?.status) queryParams.set("status", filters.status);

  const queryString = queryParams.toString();
  const url = token
    ? `/manufacturer-portal/order-items${queryString ? `?${queryString}` : ""}`
    : null;

  const { data, error, isLoading, isValidating, mutate } = useSWR<ManufacturerOrderItemsResponse>(
    url,
    fetcher,
    {
      keepPreviousData: true,
    }
  );

  return {
    data,
    items: data?.items ?? [],
    total: data?.total ?? 0,
    totalQuantity: data?.total_quantity ?? 0,
    totalAmount: data?.total_amount ?? 0,
    isLoading: token === null || isLoading, // トークン取得前もloading扱い
    // フィルター変更中はisValidatingがtrueになる（データ再取得中）
    isFiltering: isValidating && !isLoading,
    error,
    mutate,
  };
}

/**
 * メーカー単位で全発注資料をダウンロード（ZIP形式）
 * ログイン中のメーカーの全発注中アイテムを含むZIPを取得します
 */
export async function downloadAllOrderDocuments(
  filters?: ManufacturerOrderFilters,
  orderItemIds?: string[]
): Promise<Blob> {
  const token = localStorage.getItem("manufacturer_token");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const params = new URLSearchParams();
  if (filters?.search) params.set("search", filters.search);
  if (filters?.status) params.set("status", filters.status);
  if (orderItemIds?.length) params.set("order_item_ids", orderItemIds.join(","));

  const queryString = params.toString();
  const url = `${apiUrl}/manufacturer-portal/order-documents${queryString ? `?${queryString}` : ""}`;

  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new Error("Download failed");
  }
  return response.blob();
}
