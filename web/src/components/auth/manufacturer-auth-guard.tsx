"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { PageLoading } from "@/components/common/loading-spinner";

interface ManufacturerAuthGuardProps {
  children: React.ReactNode;
  onAuthenticated?: (manufacturerName: string) => void;
}

export function ManufacturerAuthGuard({ children, onAuthenticated }: ManufacturerAuthGuardProps) {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("manufacturer_token");
    const name = localStorage.getItem("manufacturer_name");

    if (!token) {
      router.replace("/manufacturer-login");
    } else {
      setIsAuthenticated(true);
      if (onAuthenticated && name) {
        onAuthenticated(name);
      }
    }
  }, [router, onAuthenticated]);

  if (isAuthenticated === null) {
    return <PageLoading />;
  }

  return <>{children}</>;
}
