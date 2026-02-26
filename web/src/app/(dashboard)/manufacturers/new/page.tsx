"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { ManufacturerForm } from "@/features/manufacturers/components/manufacturer-form";

export default function NewManufacturerPage() {
  const router = useRouter();

  const handleSuccess = () => {
    router.push("/manufacturers");
  };

  const handleCancel = () => {
    router.push("/manufacturers");
  };

  return (
    <PageContainer
      title="メーカー登録"
      description="メーカーを新規登録します"
      actions={
        <Button variant="outline" onClick={() => router.push("/manufacturers")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          メーカー一覧に戻る
        </Button>
      }
    >
      <ManufacturerForm onSuccess={handleSuccess} onCancel={handleCancel} />
    </PageContainer>
  );
}
