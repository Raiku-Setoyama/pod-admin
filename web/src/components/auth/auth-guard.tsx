"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { PageLoading } from "@/components/common/loading-spinner";

interface AuthGuardProps {
  children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");

    if (!token) {
      // 未認証の場合はログインページへリダイレクト
      router.replace(`/login?redirect=${encodeURIComponent(pathname)}`);
    } else {
      setIsAuthenticated(true);
    }
  }, [router, pathname]);

  // 認証チェック中はローディング表示
  if (isAuthenticated === null) {
    return <PageLoading />;
  }

  // 認証済みの場合はchildrenを表示
  return <>{children}</>;
}
