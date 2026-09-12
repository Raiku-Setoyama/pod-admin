"use client";

import { useCallback, useState } from "react";
import { useRouter, useSearchParams, usePathname } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/layout/page-container";
import { Pagination } from "@/components/common/pagination";
import { PageLoading } from "@/components/common/loading-spinner";
import { apiClient } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { ManufacturingDataList } from "@/features/manufacturing-data/components/manufacturing-data-list";
import { useManufacturingData } from "@/features/manufacturing-data/hooks/use-manufacturing-data";
import type { ManufacturingDataStatus } from "@/types/api";

const statusFilters: { value: ManufacturingDataStatus | null; label: string }[] = [
  { value: null, label: "すべて" },
  { value: "failed", label: "生成失敗" },
  { value: "pending", label: "生成待ち" },
  { value: "generating", label: "生成中" },
  { value: "ready", label: "完成" },
];

const validStatuses: ManufacturingDataStatus[] = [
  "pending",
  "generating",
  "ready",
  "failed",
];

/**
 * 製造データの状態を一覧し、失敗した行をまとめて生成待ちへ戻す画面。
 *
 * **これが無いと、生成の失敗に気づく手段が「発注できないという問い合わせ」しかない。**
 * 受注画面は 1 注文ずつしか見えず、失敗した行を横断して探せなかった。
 */
export default function ManufacturingDataPage() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isRetrying, setIsRetrying] = useState(false);

  const rawStatus = searchParams.get("status");
  const status =
    rawStatus && validStatuses.includes(rawStatus as ManufacturingDataStatus)
      ? (rawStatus as ManufacturingDataStatus)
      : null;
  const page = Number(searchParams.get("page")) || 1;
  const limit = Number(searchParams.get("limit")) || 20;

  const { items, total, statusCounts, isLoading, mutate } = useManufacturingData({
    page,
    limit,
    status,
  });

  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null) params.delete(key);
        else params.set(key, value);
      }
      const queryString = params.toString();
      router.replace(`${pathname}${queryString ? `?${queryString}` : ""}`);
    },
    [searchParams, router, pathname],
  );

  const selectableIds = items.filter((i) => i.status === "failed").map((i) => i.id);

  const toggle = (id: string) =>
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );

  const toggleAll = () =>
    setSelectedIds((current) =>
      selectableIds.every((id) => current.includes(id)) ? [] : selectableIds,
    );

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
          {statusFilters.map((filter) => {
            const count = filter.value ? statusCounts[filter.value] : undefined;
            return (
              <Button
                key={filter.label}
                variant={status === filter.value ? "default" : "outline"}
                size="sm"
                onClick={() =>
                  updateSearchParams({ status: filter.value, page: null })
                }
              >
                {filter.label}
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
              onToggle={toggle}
              onToggleAll={toggleAll}
              selectableIds={selectableIds}
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
