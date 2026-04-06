import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ProductAttributeSpec, ProductType } from "@/types/api";

export function useProductAttributeSpec(productType: ProductType | null) {
  const { data, error, isLoading, mutate } = useSWR<ProductAttributeSpec>(
    productType ? `/product-attributes/${productType}/spec` : null,
    apiClient
  );

  return {
    spec: data ?? null,
    isLoading,
    error,
    mutate,
  };
}
