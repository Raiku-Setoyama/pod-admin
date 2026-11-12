"use client";

import { useMemo, useState } from "react";
import { ChevronRight, Search, X } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { groupDataExportColumns } from "@/features/data-export/utils/build-data-export-request";
import type { DataExportColumn } from "@/types/api";

interface ColumnPickerProps {
  columns: DataExportColumn[];
  selectedKeys: ReadonlySet<string>;
  onToggle: (keys: string[], checked: boolean) => void;
  className?: string;
}

/**
 * 出力する項目を選ぶ一覧。
 *
 * 分類ごとに折りたたんで並べ、開いた分類の項目だけを見せる。
 * キーワードを入れると、表示名・分類名に当てはまる項目だけを分類を開いた状態で見せる。
 */
export function ColumnPicker({ columns, selectedKeys, onToggle, className }: ColumnPickerProps) {
  const [query, setQuery] = useState("");
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  const groups = useMemo(() => groupDataExportColumns(columns), [columns]);
  const normalizedQuery = query.trim().toLowerCase();
  const isSearching = normalizedQuery !== "";

  const visibleGroups = useMemo(() => {
    if (!isSearching) return groups;
    return groups
      .map(({ group, columns: groupColumns }) => ({
        group,
        columns: group.toLowerCase().includes(normalizedQuery)
          ? groupColumns
          : groupColumns.filter((c) => c.label.toLowerCase().includes(normalizedQuery)),
      }))
      .filter((g) => g.columns.length > 0);
  }, [groups, isSearching, normalizedQuery]);

  const toggleGroupOpen = (group: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(group)) next.delete(group);
      else next.add(group);
      return next;
    });
  };

  return (
    <div className={cn("flex min-h-0 flex-col", className)}>
      <div className="relative p-3 pb-2">
        <Search className="absolute left-6 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="項目名で探す（例: 住所、メーカー）"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="h-9 pl-9 pr-9"
          aria-label="項目を検索"
        />
        {isSearching && (
          <button
            type="button"
            onClick={() => setQuery("")}
            className="absolute right-5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground hover:bg-muted"
            aria-label="項目の検索をクリア"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3" role="group" aria-label="出力する項目">
        {visibleGroups.length === 0 && (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">
            「{query.trim()}」に当てはまる項目はありません
          </p>
        )}
        {visibleGroups.map(({ group, columns: groupColumns }) => {
          const allKeys = (groups.find((g) => g.group === group)?.columns ?? []).map(
            (c) => c.key
          );
          const visibleKeys = groupColumns.map((c) => c.key);
          const checkedCount = allKeys.filter((k) => selectedKeys.has(k)).length;
          const visibleChecked = visibleKeys.filter((k) => selectedKeys.has(k)).length;
          const groupState =
            visibleChecked === 0
              ? false
              : visibleChecked === visibleKeys.length
                ? true
                : "indeterminate";
          const isOpen = isSearching || openGroups.has(group);
          const listId = `column-group-${group}`;

          return (
            <section key={group} className="mb-1">
              <div className="flex items-center gap-1 rounded-md pr-2 hover:bg-muted/60">
                <button
                  type="button"
                  onClick={() => toggleGroupOpen(group)}
                  disabled={isSearching}
                  aria-expanded={isOpen}
                  aria-controls={listId}
                  className="flex min-w-0 flex-1 items-center gap-1.5 px-2 py-2 text-left text-sm font-semibold disabled:cursor-default"
                >
                  <ChevronRight
                    className={cn(
                      "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                      isOpen && "rotate-90"
                    )}
                  />
                  <span className="truncate">{group}</span>
                  <span
                    className={cn(
                      "ml-auto shrink-0 rounded-full px-1.5 text-xs font-normal tabular-nums",
                      checkedCount > 0
                        ? "bg-primary/10 text-primary"
                        : "text-muted-foreground"
                    )}
                  >
                    {checkedCount}/{allKeys.length}
                  </span>
                </button>
                <Checkbox
                  checked={groupState}
                  onCheckedChange={(checked) => onToggle(visibleKeys, checked === true)}
                  aria-label={
                    isSearching
                      ? `${group}の当てはまる項目をすべて選択`
                      : `${group}をすべて選択`
                  }
                />
              </div>

              {isOpen && (
                <ul id={listId} className="mb-2 ml-5 border-l pl-2">
                  {groupColumns.map((column) => {
                    const id = `column-${column.key}`;
                    return (
                      <li key={column.key}>
                        <label
                          htmlFor={id}
                          className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/60"
                        >
                          <Checkbox
                            id={id}
                            checked={selectedKeys.has(column.key)}
                            onCheckedChange={(checked) => onToggle([column.key], checked === true)}
                          />
                          <span>{column.label}</span>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
