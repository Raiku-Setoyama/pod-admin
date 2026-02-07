"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";
import { PageContainer } from "@/components/layout/page-container";
import { LoadingSpinner } from "@/components/common/loading-spinner";
import { ManufacturerChat } from "@/features/manufacturers/components/manufacturer-chat";
import { apiClient } from "@/lib/api/client";

interface Manufacturer {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  is_active: boolean;
}

const fetcher = async (url: string) => {
  return apiClient<Manufacturer>(url);
};

export default function ManufacturerChatPage() {
  const params = useParams();
  const router = useRouter();
  const manufacturerId = params.id as string;

  const { data: manufacturer, isLoading } = useSWR<Manufacturer>(
    `/manufacturers/${manufacturerId}`,
    fetcher
  );

  if (isLoading) {
    return (
      <PageContainer title="チャット" description="読み込み中...">
        <div className="flex items-center justify-center py-12">
          <LoadingSpinner />
        </div>
      </PageContainer>
    );
  }

  if (!manufacturer) {
    return (
      <PageContainer title="チャット" description="メーカーが見つかりません">
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
      title={`${manufacturer.name} とのチャット`}
      description="メーカーとのメッセージのやり取りができます"
      actions={
        <Button variant="outline" onClick={() => router.push("/manufacturers")}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          メーカー一覧に戻る
        </Button>
      }
    >
      <ManufacturerChat
        manufacturerId={manufacturerId}
        manufacturerName={manufacturer.name}
      />
    </PageContainer>
  );
}
