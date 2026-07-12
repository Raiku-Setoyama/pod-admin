"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import type { ManufacturingDataStatus, OrderItemStatus } from "@/types/api";

/**
 * 製造データを製造着手前（発注準備中/発注済み）に再作成できるか。
 * v2（製造データ紐付けあり）かつ ready/failed の行のみ対象。生成中/生成待ちは不可。
 * 受注詳細・メーカー発注詳細で共有する（型が異なるためプリミティブを受け取る）。
 */
export function canRegenerateManufacturingData(
  itemStatus: OrderItemStatus | undefined,
  mfgStatus: ManufacturingDataStatus | null | undefined,
  manufacturingDataId: string | null | undefined,
): boolean {
  if (!manufacturingDataId || !mfgStatus) return false;
  const preManufacturing =
    itemStatus === "preparing_order" || itemStatus === "ordered";
  const regenerable = mfgStatus === "ready" || mfgStatus === "failed";
  return preManufacturing && regenerable;
}

/**
 * 製造データ再作成 API を叩くフック（進行中 ID の state・トースト・完了コールバックを一元管理）。
 * 共有ブロック（製造中/納入済みと共有）は 409 を返すため、その旨をエラートーストで案内する。
 */
export function useRegenerateManufacturingData(onDone?: () => void) {
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

  const regenerate = async (mfgId: string) => {
    setRegeneratingId(mfgId);
    try {
      await apiClient(`/manufacturing-data/${mfgId}/regenerate`, { method: "POST" });
      toast.success("製造データを再作成しました（生成完了までしばらくお待ちください）");
      onDone?.();
    } catch {
      toast.error(
        "製造データを再作成できませんでした。製造中/納品済みの注文と共有されている場合は再作成できません。",
      );
    } finally {
      setRegeneratingId(null);
    }
  };

  return { regeneratingId, regenerate };
}

interface ManufacturingRegenerateControlsProps {
  itemStatus: OrderItemStatus | undefined;
  mfgStatus: ManufacturingDataStatus | null | undefined;
  manufacturingDataId: string | null | undefined;
  /** 生成失敗時の詳細（要対応バッジの tooltip に表示）。 */
  errorMessage?: string | null;
  regeneratingId: string | null;
  onRegenerate: (mfgId: string) => void;
}

/**
 * 統合ステータスに添える「⚠要対応（生成失敗）」表示と「再作成」ボタン。
 * 受注詳細・メーカー発注詳細のステータス列で共有する。
 */
export function ManufacturingRegenerateControls({
  itemStatus,
  mfgStatus,
  manufacturingDataId,
  errorMessage,
  regeneratingId,
  onRegenerate,
}: ManufacturingRegenerateControlsProps) {
  const showRegenerate = canRegenerateManufacturingData(
    itemStatus,
    mfgStatus,
    manufacturingDataId,
  );

  return (
    <>
      {mfgStatus === "failed" && (
        <span
          className="inline-flex items-center gap-1 text-xs font-medium text-red-600"
          title={errorMessage ?? "製造データの生成に失敗しました"}
        >
          <AlertTriangle className="h-3.5 w-3.5" />
          要対応
        </span>
      )}
      {showRegenerate && manufacturingDataId && (
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-2"
          onClick={() => onRegenerate(manufacturingDataId)}
          disabled={regeneratingId === manufacturingDataId}
          title="製造データを再作成する（製造着手前のみ）"
        >
          <RefreshCw
            className={cn(
              "h-3.5 w-3.5",
              regeneratingId === manufacturingDataId && "animate-spin",
            )}
          />
          <span className="ml-1">再作成</span>
        </Button>
      )}
    </>
  );
}
