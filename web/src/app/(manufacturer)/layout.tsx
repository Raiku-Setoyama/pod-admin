"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { ManufacturerSidebar } from "@/components/layout/manufacturer-sidebar";
import { ManufacturerAuthGuard } from "@/components/auth/manufacturer-auth-guard";

export default function ManufacturerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [manufacturerName, setManufacturerName] = useState<string>("");

  // ログインページの場合はサイドバーと認証ガードを適用しない
  if (pathname === "/manufacturer-login") {
    return (
      <div className="min-h-screen bg-gray-50">
        {children}
      </div>
    );
  }

  return (
    <ManufacturerAuthGuard onAuthenticated={setManufacturerName}>
      <div className="flex h-screen bg-gray-50">
        <ManufacturerSidebar manufacturerName={manufacturerName} />
        <main className="flex-1 overflow-y-auto p-8">{children}</main>
      </div>
    </ManufacturerAuthGuard>
  );
}
