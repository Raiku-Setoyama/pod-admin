import { useEffect, useState } from "react";
import useSWR from "swr";
import { apiClient } from "@/lib/api/client";
import type {
  DataExportCsvRequest,
  DataExportPreviewRequest,
  DataExportPreviewResponse,
} from "@/types/api";

const PREVIEW_DEBOUNCE_MS = 400;

function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

/** 出力条件（項目・絞り込み・並び順）を 1 つの文字列にする。項目が 0 個なら null。 */
export function dataExportRequestKey(request: DataExportCsvRequest): string | null {
  return request.columns.length > 0 ? JSON.stringify(request) : null;
}

/**
 * 出力内容のプレビュー（指定したページの行と件数）。
 *
 * 項目のチェックやキーワード入力のたびに叩かないよう、出力条件は落ち着いてから取りに行く。
 * ページの切り替えは待たずにすぐ取りに行く。
 * 項目が 0 個のときは取りに行かない（API も 422 を返す）。
 */
export function useDataExportPreview(request: DataExportCsvRequest, page: number, limit: number) {
  const key = dataExportRequestKey(request);
  const debouncedKey = useDebouncedValue(key, PREVIEW_DEBOUNCE_MS);

  const { data, error, isLoading, isValidating } = useSWR<DataExportPreviewResponse>(
    debouncedKey ? ["/data-export/preview", debouncedKey, page, limit] : null,
    ([endpoint, body, p, l]: [string, string, number, number]) =>
      apiClient<DataExportPreviewResponse>(endpoint, {
        method: "POST",
        body: {
          ...(JSON.parse(body) as DataExportCsvRequest),
          page: p,
          limit: l,
        } satisfies DataExportPreviewRequest,
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
