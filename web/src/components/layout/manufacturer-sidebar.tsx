"use client";

import { useRouter } from "next/navigation";
import { Package, MessageSquare, Factory, Settings } from "lucide-react";
import { BaseSidebar, type NavItem } from "./base-sidebar";

const navigation: NavItem[] = [
  { name: "発注", href: "/manufacturer", icon: Package },
  { name: "チャット", href: "/manufacturer/chat", icon: MessageSquare },
  { name: "アカウント設定", href: "/manufacturer/settings", icon: Settings },
];

interface ManufacturerSidebarProps {
  manufacturerName?: string;
}

export function ManufacturerSidebar({ manufacturerName }: ManufacturerSidebarProps) {
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("manufacturer_token");
    localStorage.removeItem("manufacturer_refresh_token");
    localStorage.removeItem("manufacturer_id");
    localStorage.removeItem("manufacturer_name");
    router.push("/manufacturer-login");
  };

  return (
    <BaseSidebar
      title="メーカー専用"
      titleIcon={Factory}
      navigation={navigation}
      userInfo={manufacturerName}
      onLogout={handleLogout}
    />
  );
}
