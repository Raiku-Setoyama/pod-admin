import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type {
  ManufacturingDataListResponse,
  ManufacturingDataStatus,
} from "@/types/api";

interface UseManufacturingDataParams {
  page?: number;
  limit?: number;
  status?: ManufacturingDataStatus | null;
  product_code?: string | null;
}

/**
 * 製造データ一覧を取得する。
 *
 * 生成待ち・生成中の行は外部 VM の処理につれて変わるので、画面を開いたまま放置しても
 * 状況が追えるよう定期的に取り直す。**これが「気づく」側の唯一の手段である**
 * （生成の失敗は受注画面に出ないため、ここを見ないと分からない）。
 */
export function useManufacturingData(params: UseManufacturingDataParams = {}) {
  const { page = 1, limit = 20, status, product_code } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (status) queryParams.set("status", status);
  if (product_code) queryParams.set("product_code", product_code);

  const { data, error, isLoading, mutate } = useSWR<ManufacturingDataListResponse>(
    `/manufacturing-data?${queryParams.toString()}`,
    apiClient,
    { refreshInterval: 30_000 },
  );

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    page: data?.page ?? page,
    limit: data?.limit ?? limit,
    statusCounts: data?.status_counts ?? {},
    isLoading,
    error,
    mutate,
  };
}
