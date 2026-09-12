"use client";

import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { useSearchParamUpdater } from "@/lib/use-search-param-updater";
import {
  getManufacturingDataFilterOptions,
  isManufacturingDataStatus,
} from "@/constants/status";
import { ManufacturingDataList } from "@/features/manufacturing-data/components/manufacturing-data-list";
import { useManufacturingData } from "@/features/manufacturing-data/hooks/use-manufacturing-data";

const filterOptions = getManufacturingDataFilterOptions();

/**
 * 製造データの状態を一覧し、失敗した行をまとめて生成待ちへ戻す画面。
 *
 * **これが無いと、生成の失敗に気づく手段が「発注できないという問い合わせ」しかない。**
 * 受注画面は 1 注文ずつしか見えず、失敗した行を横断して探せなかった。
 */
export default function ManufacturingDataPage() {
  const searchParams = useSearchParams();
  const updateSearchParams = useSearchParamUpdater();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isRetrying, setIsRetrying] = useState(false);

  const rawStatus = searchParams.get("status");
  const status = isManufacturingDataStatus(rawStatus) ? rawStatus : null;
  const page = Number(searchParams.get("page")) || 1;
  const limit = Number(searchParams.get("limit")) || 20;

  const { items, total, statusCounts, isLoading, mutate } = useManufacturingData({
    page,
    limit,
    status,
  });

  /**
   * 失敗した行を生成待ちへ戻す。選択が無ければ failed の全件が対象になる。
   *
   * VM が止まっていた間に溜まった失敗を 1 件ずつ叩かずに戻すための操作である。
   */
  const retryFailed = async (ids: string[] | null) => {
    setIsRetrying(true);
    try {
      const result = await apiClient<{ restored: number }>(
        "/manufacturing-data/retry-failed",
        { method: "POST", body: { ids } },
      );
      toast.success(
        `${result.restored} 件を生成待ちに戻しました（ワーカーが順に生成します）`,
      );
      setSelectedIds([]);
      await mutate();
    } catch {
      toast.error("生成待ちに戻せませんでした");
    } finally {
      setIsRetrying(false);
    }
  };

  const failedCount = statusCounts.failed ?? 0;

  return (
    <PageContainer
      title="製造データ"
      description="外部 VM での製造データ生成の状態を確認し、失敗した生成を戻します"
      actions={
        <Button variant="outline" onClick={() => mutate()} disabled={isLoading}>
          <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          更新
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          {filterOptions.map((option) => {
            const value = option.value === "all" ? null : option.value;
            const count = value ? statusCounts[value] : undefined;
            return (
              <Button
                key={option.value}
                variant={status === value ? "default" : "outline"}
                size="sm"
                onClick={() => updateSearchParams({ status: value, page: null })}
              >
                {option.label}
                {count !== undefined && count > 0 && (
                  <span className="ml-1.5 text-xs opacity-80">{count}</span>
                )}
              </Button>
            );
          })}
        </div>

        {failedCount > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3">
            <p className="text-sm">
              <span className="font-medium text-destructive">
                生成に失敗した製造データが {failedCount} 件あります。
              </span>{" "}
              <span className="text-muted-foreground">
                原因が解消していれば、生成待ちへ戻すと自動で作り直されます。
              </span>
            </p>
            <div className="flex items-center gap-2">
              {selectedIds.length > 0 && (
                <Button
                  size="sm"
                  onClick={() => retryFailed(selectedIds)}
                  disabled={isRetrying}
                >
                  <RotateCcw className="h-4 w-4" />
                  選択した {selectedIds.length} 件を戻す
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => retryFailed(null)}
                disabled={isRetrying}
              >
                <RotateCcw className={cn("h-4 w-4", isRetrying && "animate-spin")} />
                失敗した全 {failedCount} 件を戻す
              </Button>
            </div>
          </div>
        )}

        {isLoading ? (
          <PageLoading />
        ) : (
          <>
            <ManufacturingDataList
              items={items}
              selectedIds={selectedIds}
              onSelectChange={setSelectedIds}
            />
            <Pagination
              page={page}
              limit={limit}
              total={total}
              onPageChange={(p) =>
                updateSearchParams({ page: p > 1 ? String(p) : null })
              }
              onLimitChange={(l) =>
                updateSearchParams({
                  limit: l !== 20 ? String(l) : null,
                  page: null,
                })
              }
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
