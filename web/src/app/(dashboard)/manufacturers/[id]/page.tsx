"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ManufacturerForm } from "@/features/manufacturers/components/manufacturer-form";
import { apiClient } from "@/lib/api/client";
import type { Manufacturer } from "@/types/api";

const fetcher = (url: string) => apiClient<Manufacturer>(url);

export default function ManufacturerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const manufacturerId = params.id as string;

  const { data: manufacturer, isLoading, error } = useSWR<Manufacturer>(
    `/manufacturers/${manufacturerId}`,
    fetcher
  );

  const handleSuccess = () => {
    router.push("/manufacturers");
  };

  const handleCancel = () => {
    router.push("/manufacturers");
  };

  if (isLoading) {
    return (
      <PageContainer title="メーカー編集" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  if (error || !manufacturer) {
    return (
      <PageContainer title="メーカー編集" description="エラーが発生しました">
        <div className="text-center py-12">
          <p className="text-muted-foreground">メーカーが見つかりません</p>
          <Button variant="outline" onClick={() => router.back()} className="mt-4">
            戻る
          </Button>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title={`メーカー編集: ${manufacturer.name}`}
      description="メーカー情報を編集します"
      actions={
        <Button variant="outline" onClick={() => router.push("/manufacturers")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          メーカー一覧に戻る
        </Button>
      }
    >
      <ManufacturerForm
        manufacturer={manufacturer}
        onSuccess={handleSuccess}
        onCancel={handleCancel}
      />
    </PageContainer>
  );
}
