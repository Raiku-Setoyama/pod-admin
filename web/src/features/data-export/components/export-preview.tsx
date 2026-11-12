"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Loader2, TableProperties } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DataExportPreviewResponse, DataExportSortDirection } from "@/types/api";

interface ExportPreviewProps {
  preview: DataExportPreviewResponse | undefined;
  hasColumns: boolean;
  isUpdating: boolean;
  hasError: boolean;
  /** 見出し（表示名）から項目のキーを引く。見つからない見出しは並べ替えできない */
  keyByLabel: ReadonlyMap<string, string>;
  sortColumn: string | null;
  sortDirection: DataExportSortDirection;
  /** 見出しのクリック。指定なし → 昇順 → 降順 → 指定なし の順に切り替える */
  onSortChange: (column: string | null, direction: DataExportSortDirection) => void;
}

/** 出力される CSV の先頭の数行を表で見せる。見出しをクリックすると並べ替える。 */
export function ExportPreview({
  preview,
  hasColumns,
  isUpdating,
  hasError,
  keyByLabel,
  sortColumn,
  sortDirection,
  onSortChange,
}: ExportPreviewProps) {
  const cycleSort = (key: string) => {
    if (sortColumn !== key) onSortChange(key, "asc");
    else if (sortDirection === "asc") onSortChange(key, "desc");
    else onSortChange(null, "asc");
  };

  if (!hasColumns) {
    return (
      <EmptyState>
        <TableProperties className="h-8 w-8 text-muted-foreground/60" />
        <p>左の一覧から出力する項目を選ぶと、ここに出力内容のプレビューが出ます</p>
      </EmptyState>
    );
  }

  if (hasError && !preview) {
    return (
      <EmptyState>
        <p className="text-destructive">プレビューを読み込めませんでした</p>
      </EmptyState>
    );
  }

  if (!preview) {
    return (
      <EmptyState>
        <Loader2 className="h-5 w-5 animate-spin" />
        <p>プレビューを読み込み中...</p>
      </EmptyState>
    );
  }

  return (
    <div
      className={
        "relative min-h-0 flex-1 overflow-auto transition-opacity" +
        (isUpdating ? " opacity-60" : "")
      }
      aria-busy={isUpdating}
    >
      <table className="w-max min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className="sticky left-0 top-0 z-20 border-b border-r bg-muted px-3 py-2 text-right text-xs font-medium text-muted-foreground">
              #
            </th>
            {preview.headers.map((header, i) => {
              const key = keyByLabel.get(header);
              const sorted = key !== undefined && key === sortColumn;
              const SortIcon = sorted ? (sortDirection === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
              return (
                <th
                  key={`${header}-${i}`}
                  scope="col"
                  aria-sort={
                    sorted ? (sortDirection === "asc" ? "ascending" : "descending") : undefined
                  }
                  className="sticky top-0 z-10 whitespace-nowrap border-b bg-muted p-0 text-left font-medium"
                >
                  {key === undefined ? (
                    <span className="block px-3 py-2">{header}</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => cycleSort(key)}
                      className={cn(
                        "group flex w-full items-center gap-1 px-3 py-2 hover:bg-muted-foreground/10",
                        sorted && "text-primary"
                      )}
                      title="クリックで並べ替え"
                    >
                      {header}
                      <SortIcon
                        className={cn(
                          "h-3 w-3",
                          sorted ? "opacity-100" : "opacity-0 group-hover:opacity-50"
                        )}
                      />
                    </button>
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {preview.rows.length === 0 ? (
            <tr>
              <td
                colSpan={preview.headers.length + 1}
                className="px-3 py-10 text-center text-muted-foreground"
              >
                絞り込みに当てはまるデータがありません（出力するとヘッダ行だけの CSV になります）
              </td>
            </tr>
          ) : (
            preview.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-muted/40">
                <td className="sticky left-0 border-b border-r bg-card px-3 py-1.5 text-right text-xs tabular-nums text-muted-foreground">
                  {rowIndex + 1}
                </td>
                {row.map((value, i) => (
                  <td
                    key={i}
                    className="max-w-[280px] truncate whitespace-nowrap border-b px-3 py-1.5"
                    title={value}
                  >
                    {value === "" ? <span className="text-muted-foreground/50">—</span> : value}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-[200px] flex-1 flex-col items-center justify-center gap-2 px-6 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}
