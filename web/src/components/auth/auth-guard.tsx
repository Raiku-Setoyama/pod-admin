"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { PageLoading } from "@/components/common/loading-spinner";
import {
  isTokenExpired,
  refreshAccessToken,
  clearTokens,
} from "@/lib/api/client";

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem("access_token");

      if (!token) {
        // トークンなし：ログインページへリダイレクト
        router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
        return;
      }

      // トークンの有効期限をチェック（60秒のバッファ付き）
      if (isTokenExpired(token, 60)) {
        // トークンが期限切れまたは期限切れ間近：リフレッシュを試みる
        const refreshed = await refreshAccessToken();

        if (!refreshed) {
          // リフレッシュ失敗：トークンをクリアしてログインページへ
          clearTokens();
          router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
          return;
        }
      }

      setIsAuthenticated(true);
    };

    checkAuth();
  }, [router, pathname]);

  // 認証チェック中はローディング表示
  if (isAuthenticated === null) {
    return <PageLoading />;
  }

  // 認証済みの場合はchildrenを表示
  return <>{children}</>;
}
