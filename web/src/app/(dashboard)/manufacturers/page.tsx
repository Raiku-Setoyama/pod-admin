"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { ManufacturerList } from "@/features/manufacturers/components/manufacturer-list";
import { useManufacturers } from "@/features/manufacturers/hooks/use-manufacturers";
import type { Manufacturer } from "@/types/api";

export default function ManufacturersPage() {
  const router = useRouter();
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(20);

  const { manufacturers, total, isLoading } = useManufacturers({
    page,
    limit,
  });

  const handleRowClick = (manufacturer: Manufacturer) => {
    router.push(`/manufacturers/${manufacturer.id}`);
  };

  return (
    <PageContainer
      title="メーカー一覧"
      description="取引メーカーの管理"
      actions={
        <Button onClick={() => router.push("/manufacturers/new")}>
          <Plus className="h-4 w-4" />
          新規メーカー
        </Button>
      }
    >
      <div className="space-y-4">
        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ManufacturerList manufacturers={manufacturers} onRowClick={handleRowClick} />
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
