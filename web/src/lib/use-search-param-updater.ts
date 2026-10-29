"use client";

import { useCallback } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/**
 * 一覧画面の絞り込み・ページングを URL のクエリに反映するための更新関数を返す。
 *
 * 値に `null` を渡すとそのキーを消す（＝既定値に戻す）。**既定値をクエリに残さない**
 * ことで、共有された URL が「いま画面に見えているもの」と一致する。
 *
 * `router.replace` を使うのは、絞り込みのたびに履歴を積むと戻るボタンが
 * 使い物にならなくなるためである。
 */
export function useSearchParamUpdater(): (
  updates: Record<string, string | null>
) => void {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  return useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null) {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      const queryString = params.toString();
      router.replace(`${pathname}${queryString ? `?${queryString}` : ""}`);
    },
    [searchParams, router, pathname]
  );
}
