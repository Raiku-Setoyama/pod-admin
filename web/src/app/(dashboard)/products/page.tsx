"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { ProductList } from "@/features/products/components/product-list";
import { useProducts } from "@/features/products/hooks/use-products";
import type { Product } from "@/types/api";

export default function ProductsPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  const { products, total, isLoading } = useProducts({
    page,
    limit,
  });

  const handleRowClick = (product: Product) => {
    router.push(`/products/${product.id}`);
  };

  return (
    <PageContainer
      title="商品マスタ"
      description="商品情報の管理"
      actions={
        <Button onClick={() => router.push("/products/new")}>
          <Plus className="h-4 w-4" />
          新規商品
        </Button>
      }
    >
      <div className="space-y-4">
        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ProductList products={products} onRowClick={handleRowClick} />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={setPage}
              onLimitChange={(newLimit) => {
                setLimit(newLimit);
                setPage(1);
              }}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
