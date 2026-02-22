import useSWR from "swr";
import { apiClient } from "@/lib/api/client";

/**
 * ユーザー情報の型定義
 */
export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "staff";
  is_active: boolean;
}

/**
 * useCurrentUser フックの戻り値の型定義
 */
export interface UseCurrentUserReturn {
  user: User | undefined;
  isLoading: boolean;
  error: Error | undefined;
  mutate: () => void;
}

/**
 * 現在ログインしているユーザー情報を取得するカスタムフック
 *
 * /auth/me エンドポイントからユーザー情報を取得し、
 * SWRによるキャッシュとリバリデーションを提供する
 */
export function useCurrentUser(): UseCurrentUserReturn {
  const { data, error, isLoading, mutate } = useSWR<User>(
    "/auth/me",
    apiClient,
    {
      revalidateOnFocus: false,
      revalidateOnReconnect: true,
      shouldRetryOnError: false,
    }
  );

  return {
    user: data,
    isLoading,
    error,
    mutate,
  };
}
