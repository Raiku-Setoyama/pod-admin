"use client";

import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import { toast } from "sonner";
import { Download, ExternalLink, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  MANUFACTURING_DATA_STATUS_COLORS,
  MANUFACTURING_DATA_STATUS_LABELS,
  ORDER_STATUS_LABELS,
} from "@/constants/status";
import { getProductTypeLabel } from "@/constants/product";
import { apiClient, downloadFile } from "@/lib/api/client";
import { cn, formatDateTime, safeExternalUrl } from "@/lib/utils";
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

/** 明細・注文のステータスの表示名（未知の値はそのまま出す）。 */
function statusLabel(status: string): string {
  return (ORDER_STATUS_LABELS as Record<string, string>)[status] ?? status;
}

function formatFileSize(bytes: number | null): string | null {
  if (bytes === null) return null;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

interface ManufacturingDataDetailSheetProps {
  /** 表示する製造データの ID。null なら閉じている。 */
  manufacturingDataId: string | null;
  onClose: () => void;
}

/**
 * 製造データ 1 件の詳細を右側に開くパネル。
 *
 * 一覧では切れてしまうエラー文の全文、生成済みファイル（.ai）、元画像、そして
 * **この製造データを使っている注文**を 1 か所で見られるようにする。製造データは
 * 複数の注文で共有されるので、失敗したときにどの注文が止まっているかはここで分かる。
 */
export function ManufacturingDataDetailSheet({
  manufacturingDataId,
  onClose,
}: ManufacturingDataDetailSheetProps) {
  const { data, error, isLoading } = useSWR<ManufacturingDataDetail>(
    manufacturingDataId ? `/manufacturing-data/${manufacturingDataId}` : null,
    apiClient,
  );

  return (
    <Sheet open={manufacturingDataId !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-xl">
        <SheetHeader>
          <SheetTitle>製造データの詳細</SheetTitle>
          <SheetDescription className="font-mono text-xs">
            {data?.product_code ?? manufacturingDataId}
          </SheetDescription>
        </SheetHeader>

        <div className="space-y-6 px-4 pb-6">
          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              読み込み中…
            </div>
          )}
          {error && !isLoading && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              詳細を取得できませんでした。時間をおいて開き直してください。
            </div>
          )}
          {data && <DetailBody detail={data} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}

function DetailBody({ detail }: { detail: ManufacturingDataDetail }) {
  const fileSize = formatFileSize(detail.file_size);

  return (
    <>
      <Section title="基本情報">
        <dl className="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-muted-foreground">ステータス</dt>
          <dd>
            <Badge
              variant="outline"
              className={cn(
                "border font-medium",
                MANUFACTURING_DATA_STATUS_COLORS[detail.status],
              )}
            >
              {MANUFACTURING_DATA_STATUS_LABELS[detail.status] ?? detail.status}
            </Badge>
          </dd>
          <dt className="text-muted-foreground">商品種別</dt>
          <dd>{getProductTypeLabel(detail.product_type)}</dd>
          <dt className="text-muted-foreground">サイズ / バリアント</dt>
          <dd>{[detail.size, detail.variant].filter(Boolean).join(" / ") || "—"}</dd>
          <dt className="text-muted-foreground">試行回数</dt>
          <dd>{detail.attempts}</dd>
          <dt className="text-muted-foreground">作成</dt>
          <dd>{formatDateTime(detail.created_at)}</dd>
          <dt className="text-muted-foreground">更新</dt>
          <dd>{formatDateTime(detail.updated_at)}</dd>
          {detail.source_images_replaced_at && (
            <>
              <dt className="text-muted-foreground">元画像の差し替え</dt>
              <dd>
                {formatDateTime(detail.source_images_replaced_at)}
                {detail.source_images_replaced_by && `（${detail.source_images_replaced_by}）`}
              </dd>
            </>
          )}
        </dl>
      </Section>

      {detail.error_message && (
        <Section title="エラー">
          <pre className="whitespace-pre-wrap break-all rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-800">
            {detail.error_message}
          </pre>
        </Section>
      )}

      <Section title="製造データ（.ai）">
        <OutputFile detail={detail} fileSize={fileSize} />
      </Section>

      <Section title="元画像">
        {detail.source_images.length === 0 ? (
          <p className="text-sm text-muted-foreground">元画像はありません</p>
        ) : (
          <ul className="space-y-2">
            {detail.source_images.map((layer) => (
              <SourceImageRow key={layer.layer_type} mfgId={detail.id} layer={layer} />
            ))}
          </ul>
        )}
      </Section>

      <Section title={`使っている注文（${detail.order_items_total} 件）`}>
        <OrderItems detail={detail} />
      </Section>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

function OutputFile({
  detail,
  fileSize,
}: {
  detail: ManufacturingDataDetail;
  fileSize: string | null;
}) {
  const [downloading, setDownloading] = useState(false);

  if (detail.status !== "ready") {
    return (
      <p className="text-sm text-muted-foreground">
        生成が終わるとダウンロードできます（現在: {MANUFACTURING_DATA_STATUS_LABELS[detail.status]}）
      </p>
    );
  }

  const filename = detail.output_filename ?? `${detail.product_code}.ai`;
  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadFile(`/manufacturing-data/${detail.id}/file`, filename);
    } catch {
      toast.error("製造データをダウンロードできませんでした");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-border p-3">
      <div className="min-w-0 text-sm">
        <div className="truncate font-mono text-xs">{filename}</div>
        {fileSize && <div className="text-xs text-muted-foreground">{fileSize}</div>}
      </div>
      <Button size="sm" variant="outline" onClick={handleDownload} disabled={downloading}>
        {downloading ? (
          <Loader2 className="mr-1 h-4 w-4 animate-spin" />
        ) : (
          <Download className="mr-1 h-4 w-4" />
        )}
        ダウンロード
      </Button>
    </div>
  );
}

function SourceImageRow({ mfgId, layer }: { mfgId: string; layer: SourceImageLayer }) {
  const [downloading, setDownloading] = useState(false);
  const externalUrl = safeExternalUrl(layer.url);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      await downloadFile(
        `/manufacturing-data/${mfgId}/source-images/${layer.layer_type}`,
        layer.filename ?? `${layer.layer_type}.png`,
      );
    } catch {
      toast.error("元画像をダウンロードできませんでした");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <li className="flex items-center justify-between gap-3 rounded-md border border-border p-3 text-sm">
      <div className="min-w-0">
        <div className="font-medium">{layerLabels[layer.layer_type] ?? layer.layer_type}</div>
        <div className="truncate text-xs text-muted-foreground">
          {layer.origin === "uploaded"
            ? `差し替え済み: ${layer.filename ?? "（ファイル名なし）"}`
            : "外部受注の元画像"}
        </div>
      </div>
      {layer.origin === "uploaded" ? (
        <Button size="sm" variant="outline" onClick={handleDownload} disabled={downloading}>
          <Download className="mr-1 h-4 w-4" />
          ダウンロード
        </Button>
      ) : (
        externalUrl && (
          <Button size="sm" variant="outline" asChild>
            <a href={externalUrl} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="mr-1 h-4 w-4" />
              開く
            </a>
          </Button>
        )
      )}
    </li>
  );
}

function OrderItems({ detail }: { detail: ManufacturingDataDetail }) {
  if (detail.order_items.length === 0) {
    return <p className="text-sm text-muted-foreground">この製造データを使っている注文はありません</p>;
  }

  const hidden = detail.order_items_total - detail.order_items.length;
  return (
    <div className="space-y-2">
      <ul className="divide-y divide-border rounded-md border border-border">
        {detail.order_items.map((ref) => (
          <li key={ref.item_id} className="flex items-center justify-between gap-3 p-3 text-sm">
            <div className="min-w-0">
              <Link
                href={`/orders/${ref.order_id}`}
                className="font-medium text-primary hover:underline"
              >
                {ref.order_number}
              </Link>
              <div className="truncate text-xs text-muted-foreground">
                {ref.product_name} × {ref.quantity} ・ {formatDateTime(ref.ordered_at)}
              </div>
            </div>
            <Badge variant="outline" className="shrink-0">
              {statusLabel(ref.item_status)}
            </Badge>
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <p className="text-xs text-muted-foreground">
          ほか {hidden} 件（新しい注文から {detail.order_items.length} 件を表示）
        </p>
      )}
    </div>
  );
}
