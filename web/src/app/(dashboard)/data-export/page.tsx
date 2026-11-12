"use client";

import { PageContainer } from "@/components/layout/page-container";
import { PageLoading } from "@/components/common/loading-spinner";
import { DataExportForm } from "@/features/data-export/components/data-export-form";
import { useDataExportColumns } from "@/features/data-export/hooks/use-data-export-columns";

export default function DataExportPage() {
  const { columns, isLoading, error } = useDataExportColumns();

  return (
    <PageContainer
      title="データ出力"
      description="項目・絞り込み・並び順を指定して CSV を出力します（1 行 = 受注明細 1 件）。配送業者へ渡す CSV は従来どおり受注一覧・配送一覧から出力してください。"
    >
      {isLoading ? (
        <PageLoading />
      ) : error ? (
        <p className="text-sm text-destructive">項目の一覧を読み込めませんでした</p>
      ) : (
        <DataExportForm columns={columns} />
      )}
    </PageContainer>
  );
}
