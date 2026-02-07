"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ProductForm } from "@/features/products/components/product-form";
import { apiClient } from "@/lib/api/client";
import type { Product, ProductType } from "@/types/api";

const productTypeLabels: Record<ProductType, string> = {
  acrylic_keychain: "アクリルキーホルダー",
  acrylic_stand: "アクリルスタンド",
  sticker: "ステッカー",
  mug: "マグカップ",
  tshirt: "Tシャツ",
};

const fetcher = (url: string) => apiClient<Product>(url);

export default function EditProductPage() {
  const params = useParams();
  const router = useRouter();
  const productId = params.id as string;

  const { data: product, isLoading, error } = useSWR<Product>(
    `/products/${productId}`,
    fetcher
  );

  const handleSuccess = () => {
    router.push("/products");
  };

  const handleCancel = () => {
    router.push("/products");
  };

  if (isLoading) {
    return (
      <PageContainer title="商品編集" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  if (error || !product) {
    return (
      <PageContainer title="商品編集" description="エラーが発生しました">
        <div className="text-center py-12">
          <p className="text-muted-foreground">商品が見つかりません</p>
          <Button variant="outline" onClick={() => router.back()} className="mt-4">
            戻る
          </Button>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={`商品編集: ${productTypeLabels[product.product_type]} ${product.size || ""}`}
      description="商品情報を編集します"
      actions={
        <Button variant="outline" onClick={() => router.push("/products")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          商品一覧に戻る
        </Button>
      }
    >
      <ProductForm
        product={product}
        onSuccess={handleSuccess}
        onCancel={handleCancel}
      />
    </PageContainer>
  );
}
