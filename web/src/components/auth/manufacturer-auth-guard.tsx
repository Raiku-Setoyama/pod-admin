"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageLoading } from "@/components/common/loading-spinner";
import { useLocalStorageValue } from "@/lib/use-local-storage-value";

interface ManufacturerAuthGuardProps {
  children: React.ReactNode;
  onAuthenticated?: (manufacturerName: string) => void;
}

export function ManufacturerAuthGuard({ children, onAuthenticated }: ManufacturerAuthGuardProps) {
  const router = useRouter();
  // 認証状態は localStorage から導出する。effect で setState すると
  // マウントのたびに余分なレンダリングが走る（set-state-in-effect）。
  const token = useLocalStorageValue("manufacturer_token");
  const name = useLocalStorageValue("manufacturer_name");

  useEffect(() => {
    // 未ログインならログイン画面へ。ハイドレーション中のサーバ側スナップショット
    // （常に null）で誤って飛ばさないよう、実際の localStorage を直接見る。
    if (!localStorage.getItem("manufacturer_token")) {
      router.replace("/manufacturer-login");
    }
  }, [router]);

  useEffect(() => {
    if (token && name && onAuthenticated) {
      onAuthenticated(name);
    }
  }, [token, name, onAuthenticated]);

  if (!token) {
    return <PageLoading />;
  }

  return <>{children}</>;
}
