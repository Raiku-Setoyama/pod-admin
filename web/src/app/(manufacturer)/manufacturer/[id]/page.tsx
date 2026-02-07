"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function ManufacturerOrderDetailPage() {
  const router = useRouter();

  useEffect(() => {
    // 発注詳細ページは廃止されたため、ダッシュボードにリダイレクト
    router.replace("/manufacturer");
  }, [router]);

  return null;
}
