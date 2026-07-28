"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { toast } from "sonner";
import { ExternalLink, Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, apiClient, fetchBlob } from "@/lib/api/client";
import type {
  ManufacturingDataDetail,
  SourceImageLayer,
  SourceImageLayerType,
} from "@/types/api";

const layerLabels: Record<SourceImageLayerType, string> = {
  color: "カラー",
  cutline: "カットライン",
  white: "白版",
  design: "デザイン",
};

function formatDateTime(value: string): string {
  return new Date(value).toLocaleString("ja-JP");
}

interface SourceImageReplaceDialogProps {
  manufacturingDataId: string;
  open: boolean;
  onClose: () => void;
  /** 差し替え完了後に一覧・詳細を再取得するためのコールバック */
  onReplaced?: () => void;
}

/**
 * 製造データの元画像（PNGレイヤー）を差し替えるダイアログ。
 *
 * 現在のレイヤー構成を取得して表示し、選択したレイヤーのみ PNG を差し替える。
 * 送信は1リクエスト（レイヤー種別と同名のファイル項目）で、再生成はサーバ側で1回だけ起動される。
 */
export function SourceImageReplaceDialog({
  manufacturingDataId,
  open,
  onClose,
  onReplaced,
}: SourceImageReplaceDialogProps) {
  const { data: detail, isLoading } = useSWR<ManufacturingDataDetail>(
    open ? `/manufacturing-data/${manufacturingDataId}` : null,
    apiClient,
  );
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // レイヤー種別 -> 差し替えるファイル
  const [selected, setSelected] = useState<Record<string, File>>({});

  useEffect(() => {
    if (!open) return;
    setSelected({});
    setError(null);
  }, [open]);

  const handleSelect = (layerType: string, file: File | undefined) => {
    if (file && file.type !== "image/png") {
      setError("元画像は PNG 形式のみ対応しています");
      return;
    }
    setError(null);
    setSelected((prev) => {
      const next = { ...prev };
      if (file) {
        next[layerType] = file;
      } else {
        delete next[layerType];
      }
      return next;
    });
  };

  const handleSubmit = async () => {
    const entries = Object.entries(selected);
    if (entries.length === 0) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const formData = new FormData();
      for (const [layerType, file] of entries) {
        formData.append(layerType, file);
      }
      await apiClient(`/manufacturing-data/${manufacturingDataId}/source-images`, {
        method: "POST",
        body: formData,
      });
      toast.success("元画像を差し替えました（製造データの再生成が完了するまでお待ちください）");
      onReplaced?.();
      onClose();
    } catch (err: unknown) {
      setError(replaceErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const selectedCount = Object.keys(selected).length;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>元画像の差し替え</DialogTitle>
          <DialogDescription>
            差し替えるレイヤーの PNG を選択してください。差し替え後、製造データは自動で再生成されます。
            同じ商品コードの他の注文にも適用されます。
          </DialogDescription>
        </DialogHeader>

        {detail?.source_images_replaced_at && (
          <p className="text-xs text-muted-foreground">
            最終差し替え: {formatDateTime(detail.source_images_replaced_at)}
            {detail.source_images_replaced_by && `（${detail.source_images_replaced_by}）`}
          </p>
        )}

        {error && (
          <div className="rounded-lg bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <div className="space-y-3">
            {detail?.source_images.map((layer) => (
              <LayerRow
                key={layer.layer_type}
                manufacturingDataId={manufacturingDataId}
                layer={layer}
                selectedFile={selected[layer.layer_type]}
                onSelect={handleSelect}
              />
            ))}
            {detail?.source_images.length === 0 && (
              <p className="py-4 text-sm text-muted-foreground">
                この製造データには元画像が登録されていません。
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
            キャンセル
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || selectedCount === 0}>
            {isSubmitting
              ? "差し替え中..."
              : `差し替えて再生成${selectedCount > 0 ? `（${selectedCount}件）` : ""}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** 差し替え失敗時に表示するメッセージ（共有ブロックとバリデーションを区別する）。 */
function replaceErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 409) {
      return "この製造データは差し替えできません（生成中、または製造中/納品済みの注文と共有されています）";
    }
    if (err.status === 400) return err.message;
  }
  return "元画像の差し替えに失敗しました";
}

interface LayerRowProps {
  manufacturingDataId: string;
  layer: SourceImageLayer;
  selectedFile: File | undefined;
  onSelect: (layerType: string, file: File | undefined) => void;
}

/** 1レイヤー分の「現在の元画像」と差し替えファイル選択。 */
function LayerRow({
  manufacturingDataId,
  layer,
  selectedFile,
  onSelect,
}: LayerRowProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const label = layerLabels[layer.layer_type];
  const [currentUrl, setCurrentUrl] = useState<string | null>(null);
  const previewUrl = useMemo(
    () => (selectedFile ? URL.createObjectURL(selectedFile) : null),
    [selectedFile],
  );

  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  // 差し替え済みレイヤーは認証付き取得が必要なため、blob URL にして表示する。
  useEffect(() => {
    if (layer.origin !== "uploaded") return;
    let objectUrl: string | null = null;
    fetchBlob(`/manufacturing-data/${manufacturingDataId}/source-images/${layer.layer_type}`)
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        setCurrentUrl(objectUrl);
      })
      .catch(() => undefined);
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [manufacturingDataId, layer.origin, layer.layer_type]);

  return (
    <div className="flex items-center gap-4 rounded-lg border p-3">
      <div className="w-24 shrink-0">
        <p className="text-sm font-medium">{label}</p>
        {layer.origin === "uploaded" && (
          <p className="text-xs text-muted-foreground">差し替え済み</p>
        )}
      </div>

      <div className="min-w-0 flex-1 text-xs text-muted-foreground">
        {layer.origin === "uploaded" ? (
          <div className="flex items-center gap-2">
            {currentUrl && (
              <img
                src={currentUrl}
                alt={`${label}の現在の元画像`}
                className="h-12 w-12 rounded border object-contain"
              />
            )}
            <span className="truncate">{layer.filename}</span>
          </div>
        ) : layer.url ? (
          <a
            href={layer.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            受注時の元画像を開く
          </a>
        ) : (
          <span>元画像なし</span>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {previewUrl && (
          <img
            src={previewUrl}
            alt={`${label}の差し替えプレビュー`}
            className="h-12 w-12 rounded border object-contain"
          />
        )}
        <input
          ref={inputRef}
          type="file"
          accept="image/png"
          className="hidden"
          aria-label={`${label}の元画像を選択`}
          onChange={(event) => onSelect(layer.layer_type, event.target.files?.[0])}
        />
        <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
          <Upload className="h-3.5 w-3.5" />
          <span className="ml-1">{selectedFile ? "変更" : "PNGを選択"}</span>
        </Button>
      </div>
    </div>
  );
}
