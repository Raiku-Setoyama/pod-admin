import { useState, useEffect } from "react";
import useSWR from "swr";
import { apiClient } from "@/lib/api/client";

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

export function useManufacturerOrderItems() {
  // useStateでトークンを管理し、変更時にSWRキーを更新させる
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    // クライアントサイドでのみlocalStorageにアクセス
    const storedToken = localStorage.getItem("manufacturer_token");
    setToken(storedToken);
  }, []);

  const { data, error, isLoading, mutate } = useSWR<ManufacturerOrderItemsResponse>(
    token ? `/manufacturer-portal/order-items` : null,
    fetcher
  );

  return {
    data,
    items: data?.items ?? [],
    total: data?.total ?? 0,
    totalQuantity: data?.total_quantity ?? 0,
    totalAmount: data?.total_amount ?? 0,
    isLoading: token === null || isLoading, // トークン取得前もloading扱い
    error,
    mutate,
  };
}

/**
 * メーカー単位で全発注資料をダウンロード（ZIP形式）
 * ログイン中のメーカーの全発注中アイテムを含むZIPを取得します
 */
export async function downloadAllOrderDocuments(): Promise<Blob> {
  const token = localStorage.getItem("manufacturer_token");
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
  const response = await fetch(`${apiUrl}/manufacturer-portal/order-documents`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    throw new Error("Download failed");
  }
  return response.blob();
}
