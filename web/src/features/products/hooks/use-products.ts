import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ProductListResponse, ProductType } from "@/types/api";

interface UseProductsParams {
  page?: number;
  limit?: number;
  product_type?: ProductType | null;
  search?: string;
}

export function useProducts(params: UseProductsParams = {}) {
  const { page = 1, limit = 20, product_type, search } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (product_type) queryParams.set("product_type", product_type);
  if (search) queryParams.set("search", search);

  const { data, error, isLoading, mutate } = useSWR<ProductListResponse>(
    `/products?${queryParams.toString()}`,
    apiClient
  );

  return {
    products: data?.items ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    isLoading,
    error,
    mutate,
  };
}
