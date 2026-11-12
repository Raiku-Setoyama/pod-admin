import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { DataExportColumnsResponse } from "@/types/api";

/**
 * データ出力で列にできる項目の一覧。
 *
 * 項目の定義（キー・表示名・分類）は API（DataExportService.EXPORT_COLUMNS）だけが持つ。
 * 画面で書き写さない。
 */
export function useDataExportColumns() {
  const { data, error, isLoading } = useSWR<DataExportColumnsResponse>(
    "/data-export/columns",
    apiClient
  );

  return {
    columns: data?.columns ?? [],
    isLoading,
    error,
  };
}
