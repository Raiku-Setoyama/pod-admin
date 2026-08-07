"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * localStorage の値を購読して返す。
 *
 * effect の中で setState してクライアント側の値を取り込むと、マウントのたびに
 * 追加のレンダリングが走る（react-hooks/set-state-in-effect）。localStorage は
 * React の外側にある store なので、useSyncExternalStore で購読するのが正しい。
 *
 * サーバレンダリング時は null を返し、ハイドレーション後に実際の値へ切り替わる。
 * 従来の「初回 null → 読み込み後に値」という見え方は変わらない。
 *
 * 購読するのは別タブでの変更（storage イベント）のみ。同一タブでの書き換えは
 * ログイン・ログアウト時に限られ、いずれも直後に画面遷移するため購読側は
 * 再マウントで最新値を読み直す。
 */
export function useLocalStorageValue(key: string): string | null {
  const subscribe = useCallback((onStoreChange: () => void) => {
    window.addEventListener("storage", onStoreChange);
    return () => window.removeEventListener("storage", onStoreChange);
  }, []);

  const getSnapshot = useCallback(() => localStorage.getItem(key), [key]);

  return useSyncExternalStore(subscribe, getSnapshot, () => null);
}
