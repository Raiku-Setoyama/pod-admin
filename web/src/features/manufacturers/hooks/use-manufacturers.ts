import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { ManufacturerListResponse } from "@/types/api";

interface UseManufacturersParams {
  page?: number;
  limit?: number;
  search?: string;
}

export function useManufacturers(params: UseManufacturersParams = {}) {
  const { page = 1, limit = 20, search } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (search) queryParams.set("search", search);

  const { data, error, isLoading, mutate } = useSWR<ManufacturerListResponse>(
    `/manufacturers?${queryParams.toString()}`,
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
