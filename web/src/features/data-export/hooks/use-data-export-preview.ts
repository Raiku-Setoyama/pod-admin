import { useEffect, useState } from "react";
import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type { DataExportCsvRequest, DataExportPreviewResponse } from "@/types/api";

const PREVIEW_DEBOUNCE_MS = 400;

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/**
 * 出力内容のプレビュー（先頭の数行と総件数）。
 *
 * 項目のチェックやキーワード入力のたびに叩かないよう、条件が落ち着いてから取りに行く。
 * 項目が 0 個のときは取りに行かない（API も 422 を返す）。
 */
export function useDataExportPreview(request: DataExportCsvRequest) {
  const key = request.columns.length > 0 ? JSON.stringify(request) : null;
  const debouncedKey = useDebouncedValue(key, PREVIEW_DEBOUNCE_MS);

  const { data, error, isLoading, isValidating } = useSWR<DataExportPreviewResponse>(
    debouncedKey ? ["/data-export/preview", debouncedKey] : null,
    ([endpoint, body]: [string, string]) =>
      apiClient<DataExportPreviewResponse>(endpoint, {
        method: "POST",
        body: JSON.parse(body),
      }),
    { keepPreviousData: true, revalidateOnFocus: false }
  );

  return {
    preview: key ? data : undefined,
    error: key ? error : undefined,
    // 入力直後（まだ取りに行っていない間）も「更新中」とみなす
    isUpdating: key !== null && (key !== debouncedKey || isLoading || isValidating),
  };
}
