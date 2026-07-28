"use client";

import { useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, ImageUp, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api/client";
import { SourceImageReplaceDialog } from "./source-image-replace-dialog";
import type { ManufacturingDataStatus, OrderItemStatus } from "@/types/api";

/**
 * 是正操作（再作成・元画像差し替え）の対象になりうる明細か。
 * v2（製造データ紐付けあり）かつ製造着手前（発注準備中/発注済み）のものだけを対象とする。
 * 受注詳細・メーカー発注詳細で共有する（型が異なるためプリミティブを受け取る）。
 */
function isCorrectableV2Item(
  itemStatus: OrderItemStatus | undefined,
  mfgStatus: ManufacturingDataStatus | null | undefined,
  manufacturingDataId: string | null | undefined,
): boolean {
  if (!manufacturingDataId || !mfgStatus) return false;
  return itemStatus === "preparing_order" || itemStatus === "ordered";
}

/**
 * 製造データを同じ元データで再作成できるか。ready/failed の行のみ対象（生成中/生成待ちは不可）。
 */
export function canRegenerateManufacturingData(
  itemStatus: OrderItemStatus | undefined,
  mfgStatus: ManufacturingDataStatus | null | undefined,
  manufacturingDataId: string | null | undefined,
): boolean {
  return (
    isCorrectableV2Item(itemStatus, mfgStatus, manufacturingDataId) &&
    (mfgStatus === "ready" || mfgStatus === "failed")
  );
}

/**
 * 元画像を差し替えられるか。生成中（進行中の VM ジョブと競合する）以外は差し替え可能で、
 * 生成待ち・生成失敗の行も是正できる（API 側のゲートと一致）。
 */
export function canReplaceSourceImages(
  itemStatus: OrderItemStatus | undefined,
  mfgStatus: ManufacturingDataStatus | null | undefined,
  manufacturingDataId: string | null | undefined,
): boolean {
  return (
    isCorrectableV2Item(itemStatus, mfgStatus, manufacturingDataId) &&
    mfgStatus !== "generating"
  );
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
  /** 元画像を差し替え済みなら差し替え時刻（バッジ表示に使用）。 */
  sourceImagesReplacedAt?: string | null;
  regeneratingId: string | null;
  onRegenerate: (mfgId: string) => void;
  /** 元画像差し替え後に親のデータを再取得するためのコールバック。 */
  onReplaced?: () => void;
}

/**
 * 統合ステータスに添える「⚠要対応（生成失敗）」表示と是正操作（再作成／元画像差し替え）。
 * 受注詳細・メーカー発注詳細のステータス列で共有する。
 */
export function ManufacturingRegenerateControls({
  itemStatus,
  mfgStatus,
  manufacturingDataId,
  errorMessage,
  sourceImagesReplacedAt,
  regeneratingId,
  onRegenerate,
  onReplaced,
}: ManufacturingRegenerateControlsProps) {
  const [replaceTargetOpen, setReplaceTargetOpen] = useState(false);
  const showRegenerate = canRegenerateManufacturingData(
    itemStatus,
    mfgStatus,
    manufacturingDataId,
  );
  const showReplace = canReplaceSourceImages(itemStatus, mfgStatus, manufacturingDataId);

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
      {sourceImagesReplacedAt && (
        <span
          className="text-xs text-muted-foreground"
          title={`元画像を差し替え済み（${new Date(sourceImagesReplacedAt).toLocaleString("ja-JP")}）`}
        >
          元画像差し替え済み
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
      {showReplace && manufacturingDataId && (
        <>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2"
            onClick={() => setReplaceTargetOpen(true)}
            title="製造データの元画像を差し替えて再生成する（製造着手前のみ）"
          >
            <ImageUp className="h-3.5 w-3.5" />
            <span className="ml-1">元画像差し替え</span>
          </Button>
          <SourceImageReplaceDialog
            manufacturingDataId={manufacturingDataId}
            open={replaceTargetOpen}
            onClose={() => setReplaceTargetOpen(false)}
            onReplaced={onReplaced}
          />
        </>
      )}
    </>
  );
}
