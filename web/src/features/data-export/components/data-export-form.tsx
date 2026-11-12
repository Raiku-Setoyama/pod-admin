"use client";

import { useMemo, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { downloadFileByPost } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { ColumnPicker } from "@/features/data-export/components/column-picker";
import { ExportPreview } from "@/features/data-export/components/export-preview";
import {
  FilterBar,
  hasActiveFilters,
  type DataExportFilterValues,
} from "@/features/data-export/components/filter-bar";
import { useDataExportPreview } from "@/features/data-export/hooks/use-data-export-preview";
import {
  buildDataExportRequest,
  dataExportFilename,
} from "@/features/data-export/utils/build-data-export-request";
import type { DataExportColumn, DataExportSortDirection } from "@/types/api";

const panelClass = "flex min-h-0 flex-col rounded-xl border bg-card shadow-sm";

const EMPTY_FILTERS: DataExportFilterValues = {
  search: "",
  status: null,
  productType: null,
  orderedRange: undefined,
  shippingRange: undefined,
};

interface DataExportFormProps {
  columns: DataExportColumn[];
}

/**
 * データ出力タブ。
 *
 * 左で列（出力する項目）を選び、右の「出力内容」で行（絞り込み）と並び順を決める。
 * 絞り込みと並び順はプレビュー表のすぐ上の条件チップと表の見出しで操作し、
 * 「この表に条件をかけると行が減る」ことが見て分かるようにしている。
 * プレビューは CSV と同じ列・並び・整形。
 */
export function DataExportForm({ columns }: DataExportFormProps) {
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState<DataExportFilterValues>(EMPTY_FILTERS);
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<DataExportSortDirection>("asc");
  const [isExporting, setIsExporting] = useState(false);

  const selectedCount = selectedKeys.size;
  const keyByLabel = useMemo(() => new Map(columns.map((c) => [c.label, c.key])), [columns]);

  const request = useMemo(
    () =>
      buildDataExportRequest(columns, {
        selectedKeys,
        ...filters,
        sortColumn,
        sortDirection,
      }),
    [columns, selectedKeys, filters, sortColumn, sortDirection]
  );
  const { preview, error: previewError, isUpdating } = useDataExportPreview(request);
  const filtered = hasActiveFilters(filters);

  const toggleKeys = (keys: string[], checked: boolean) => {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      for (const key of keys) {
        if (checked) next.add(key);
        else next.delete(key);
      }
      return next;
    });
  };

  const changeSort = (column: string | null, direction: DataExportSortDirection) => {
    setSortColumn(column);
    setSortDirection(direction);
  };

  const handleExport = async () => {
    if (selectedCount === 0) return;
    setIsExporting(true);
    try {
      await downloadFileByPost("/data-export/csv", request, dataExportFilename());
    } catch {
      toast.error("CSV の出力に失敗しました");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="grid gap-4 lg:h-full lg:min-h-0 lg:grid-cols-[300px_minmax(0,1fr)]">
      {/* 項目の一覧 */}
      <section aria-label="項目の一覧" className={`${panelClass} h-[420px] lg:h-auto`}>
        <div className="flex items-center gap-2 whitespace-nowrap border-b py-2.5 pl-4 pr-2">
          <h2 className="text-sm font-semibold">項目を選ぶ</h2>
          <span className="text-xs tabular-nums text-muted-foreground">
            {selectedCount} / {columns.length}
          </span>
          <div className="ml-auto flex items-center">
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-1.5 text-xs"
              onClick={() => toggleKeys(columns.map((c) => c.key), true)}
              disabled={selectedCount === columns.length}
            >
              すべて選択
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-1.5 text-xs"
              onClick={() => setSelectedKeys(new Set())}
              disabled={selectedCount === 0}
              aria-label="すべて解除"
            >
              解除
            </Button>
          </div>
        </div>
        <ColumnPicker
          columns={columns}
          selectedKeys={selectedKeys}
          onToggle={toggleKeys}
          className="flex-1"
        />
      </section>

      <div className="flex min-h-0 flex-col gap-4">
        {/* 出力内容：絞り込み・並び順・プレビュー・出力 */}
        <section
          aria-label="出力内容"
          className={`${panelClass} min-h-[360px] flex-1 overflow-hidden lg:min-h-[200px]`}
        >
          <div className="space-y-2 border-b px-4 py-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold">出力内容</h2>
              <span
                className="flex items-center gap-1.5 text-sm text-muted-foreground"
                aria-live="polite"
              >
                {preview && selectedCount > 0 ? (
                  <>
                    {filtered && <>{preview.unfiltered_count.toLocaleString()} 件中</>}
                    {!filtered && <>全</>}
                    <span className="font-medium tabular-nums text-foreground">
                      {preview.total_count.toLocaleString()} 件
                    </span>
                    × {selectedCount} 項目
                    {preview.total_count > preview.rows.length && (
                      <span className="text-xs">（先頭 {preview.rows.length} 件を表示）</span>
                    )}
                  </>
                ) : null}
                {isUpdating && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-label="更新中" />}
              </span>
              <Button
                size="sm"
                className="ml-auto"
                onClick={handleExport}
                disabled={selectedCount === 0 || isExporting}
              >
                <Download className="mr-1.5 h-4 w-4" />
                {isExporting ? "出力中..." : "CSV を出力"}
              </Button>
            </div>
            <FilterBar
              values={filters}
              onChange={(patch) => setFilters((prev) => ({ ...prev, ...patch }))}
              columns={columns}
              sortColumn={sortColumn}
              sortDirection={sortDirection}
              onSortChange={changeSort}
            />
          </div>

          <ExportPreview
            preview={preview}
            hasColumns={selectedCount > 0}
            isUpdating={isUpdating}
            hasError={previewError !== undefined}
            keyByLabel={keyByLabel}
            sortColumn={sortColumn}
            sortDirection={sortDirection}
            onSortChange={changeSort}
          />
        </section>
      </div>
    </div>
  );
}
