"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { ProductForm } from "@/features/products/components/product-form";

export default function NewProductPage() {
  const router = useRouter();

  const handleSuccess = () => {
    router.push("/products");
  };

  const handleCancel = () => {
    router.push("/products");
  };

  return (
    <PageContainer
      title="商品新規登録"
      description="新しい商品を登録します"
      actions={
        <Button variant="outline" onClick={() => router.push("/products")}>
          <ArrowLeft className="h-4 w-4" />
          商品一覧に戻る
        </Button>
      }
    >
      <ProductForm onSuccess={handleSuccess} onCancel={handleCancel} />
    </PageContainer>
  );
}
