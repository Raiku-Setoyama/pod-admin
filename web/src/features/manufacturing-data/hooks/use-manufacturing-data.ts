import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import { isManufacturingDataActive } from "@/constants/status";
import type {
  ManufacturingDataListResponse,
  ManufacturingDataStatus,
} from "@/types/api";

interface UseManufacturingDataParams {
  page?: number;
  limit?: number;
  status?: ManufacturingDataStatus | null;
}

/**
 * 進行中の行があるあいだだけ取り直す間隔（ミリ秒）。無ければ取り直さない。
 *
 * **止まっている状態を眺め続けない。** 生成待ち・生成中が 1 件も無ければ、
 * 人が操作しない限り状況は変わらない。それでも 30 秒ごとに叩き続けると、
 * 画面を開きっぱなしにしただけで問い合わせが積み上がる。
 */
function refreshInterval(data: ManufacturingDataListResponse | undefined): number {
  const active = data?.items.some((item) => isManufacturingDataActive(item.status));
  return active ? 15_000 : 0;
}

/**
 * 製造データ一覧を取得する。
 *
 * 生成待ち・生成中の行は外部 VM の処理につれて変わるので、画面を開いたまま放置しても
 * 状況が追えるよう定期的に取り直す。**これが「気づく」側の唯一の手段である**
 * （生成の失敗は受注画面に出ないため、ここを見ないと分からない）。
 */
export function useManufacturingData(params: UseManufacturingDataParams = {}) {
  const { page = 1, limit = 20, status } = params;

  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("limit", String(limit));
  if (status) queryParams.set("status", status);

  const { data, isLoading, mutate } = useSWR<ManufacturingDataListResponse>(
    `/manufacturing-data?${queryParams.toString()}`,
    apiClient,
    { refreshInterval },
  );

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    statusCounts: data?.status_counts ?? {},
    isLoading,
    mutate,
  };
}
