"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ShoppingCart,
  FileText,
  Truck,
  Factory,
  Package,
  MessageSquare,
  Settings,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

const navigation = [
  { name: "受注", href: "/orders", icon: ShoppingCart },
  { name: "発注", href: "/purchase-orders", icon: FileText },
  { name: "配送", href: "/shipments", icon: Truck },
  { name: "メーカー", href: "/manufacturers", icon: Factory },
  { name: "商品マスタ", href: "/products", icon: Package },
  { name: "チャット", href: "/chat", icon: MessageSquare },
];

export function Sidebar() {
  const pathname = usePathname();

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
  };

  return (
    <aside className="flex h-screen w-[200px] flex-col border-r border-border bg-white">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <Package className="h-5 w-5 text-primary-foreground" />
        </div>
        <span className="font-semibold text-foreground">グッズ管理</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navigation.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
              )}
            >
              <item.icon className="h-5 w-5" />
              {item.name}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-2">
        <div className="px-3 py-2 text-xs text-muted-foreground">
          raiku6019@gmail.com
        </div>
        <Link
          href="/settings"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <Settings className="h-5 w-5" />
          設定
        </Link>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <LogOut className="h-5 w-5" />
          ログアウト
        </button>
      </div>
    </aside>
  );
}
