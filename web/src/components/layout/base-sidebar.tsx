"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface NavItem {
  name: string;
  href: string;
  icon: LucideIcon;
}

interface BaseSidebarProps {
  title: string;
  titleIcon: LucideIcon;
  navigation: NavItem[];
  userInfo?: string;
  onLogout: () => void;
  footerNavigation?: NavItem[];
}

function isActiveNavItem(pathname: string, href: string, allHrefs: string[]): boolean {
  // 完全一致の場合はアクティブ
  if (pathname === href) return true;

  // サブパスの場合、より具体的なマッチがあるかチェック
  if (pathname.startsWith(href + "/")) {
    // 他のナビゲーション項目でより具体的なマッチがあればfalse
    const hasMoreSpecificMatch = allHrefs.some(
      (otherHref) => otherHref !== href && pathname.startsWith(otherHref) && otherHref.length > href.length
    );
    return !hasMoreSpecificMatch;
  }

  return false;
}

export function BaseSidebar({
  title,
  titleIcon: TitleIcon,
  navigation,
  userInfo,
  onLogout,
  footerNavigation,
}: BaseSidebarProps) {
  const pathname = usePathname();
  const allHrefs = [...navigation, ...(footerNavigation || [])].map((item) => item.href);

  return (
    <aside className="flex h-screen w-[200px] flex-col border-r border-border bg-white">
      {/* Logo */}
      <div className="flex h-16 items-center gap-2 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
          <TitleIcon className="h-5 w-5 text-primary-foreground" />
        </div>
        <span className="font-semibold text-foreground">{title}</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-2 py-4">
        {navigation.map((item) => {
          const isActive = isActiveNavItem(pathname, item.href, allHrefs);
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
        {userInfo && (
          <div className="px-3 py-2 text-xs text-muted-foreground truncate">
            {userInfo}
          </div>
        )}
        {footerNavigation?.map((item) => {
          const isActive = isActiveNavItem(pathname, item.href, allHrefs);
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
        <button
          onClick={onLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
        >
          <LogOut className="h-5 w-5" />
          ログアウト
        </button>
      </div>
    </aside>
  );
}
