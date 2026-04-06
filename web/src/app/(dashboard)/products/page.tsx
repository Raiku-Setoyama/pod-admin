"use client";

import { useCallback } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { ProductList } from "@/features/products/components/product-list";
import { ProductFilters } from "@/features/products/components/product-filters";
import { useProducts } from "@/features/products/hooks/use-products";
import { useManufacturers } from "@/features/manufacturers/hooks/use-manufacturers";
import type { Product, ProductType } from "@/types/api";

const validProductTypes: ProductType[] = [
  "acrylic_keychain",
  "acrylic_stand",
  "sticker",
  "tote_bag",
  "tshirt",
];

const validStatuses = ["active", "inactive"];

export default function ProductsPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Read filter values from URL search params
  const rawCategory = searchParams.get("category");
  const category = rawCategory && validProductTypes.includes(rawCategory as ProductType)
    ? rawCategory
    : null;

  const maker = searchParams.get("maker");

  const rawStatus = searchParams.get("status");
  const status = rawStatus && validStatuses.includes(rawStatus)
    ? rawStatus
    : null;

  const page = Number(searchParams.get("page")) || 1;
  const limit = Number(searchParams.get("limit")) || 20;

  // Convert status to is_active boolean for API
  const isActive = status === "active" ? true : status === "inactive" ? false : null;

  const { manufacturers } = useManufacturers({ limit: 100 });

  const { products, total, isLoading } = useProducts({
    page,
    limit,
    product_type: category as ProductType | null,
    manufacturer_id: maker,
    is_active: isActive,
  });

  // Helper to update URL search params
  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null) {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      const queryString = params.toString();
      router.replace(`${pathname}${queryString ? `?${queryString}` : ""}`);
    },
    [searchParams, router, pathname]
  );

  const handleCategoryChange = useCallback(
    (value: string | null) => {
      updateSearchParams({ category: value, page: null });
    },
    [updateSearchParams]
  );

  const handleMakerChange = useCallback(
    (value: string | null) => {
      updateSearchParams({ maker: value, page: null });
    },
    [updateSearchParams]
  );

  const handleStatusChange = useCallback(
    (value: string | null) => {
      updateSearchParams({ status: value, page: null });
    },
    [updateSearchParams]
  );

  const handleReset = useCallback(() => {
    updateSearchParams({
      category: null,
      maker: null,
      status: null,
      page: null,
    });
  }, [updateSearchParams]);

  const handlePageChange = useCallback(
    (newPage: number) => {
      updateSearchParams({ page: newPage > 1 ? String(newPage) : null });
    },
    [updateSearchParams]
  );

  const handleLimitChange = useCallback(
    (newLimit: number) => {
      updateSearchParams({
        limit: newLimit !== 20 ? String(newLimit) : null,
        page: null,
      });
    },
    [updateSearchParams]
  );

  const handleRowClick = (product: Product) => {
    router.push(`/products/${product.id}`);
  };

  return (
    <PageContainer
      title="商品マスタ"
      description="商品情報の管理"
      actions={
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => router.push("/products/attributes")}>
            属性管理
          </Button>
          <Button onClick={() => router.push("/products/new")}>
            <Plus className="h-4 w-4" />
            新規商品
          </Button>
        </div>
      }
    >
      <div className="space-y-4">
        <ProductFilters
          category={category}
          maker={maker}
          status={status}
          onCategoryChange={handleCategoryChange}
          onMakerChange={handleMakerChange}
          onStatusChange={handleStatusChange}
          onReset={handleReset}
          manufacturers={manufacturers}
        />
        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ProductList products={products} onRowClick={handleRowClick} />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={handlePageChange}
              onLimitChange={handleLimitChange}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
