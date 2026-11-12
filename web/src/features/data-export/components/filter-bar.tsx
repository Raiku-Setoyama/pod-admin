"use client";

import { useRef, useState } from "react";
import { format } from "date-fns";
import { ArrowDownUp, Check, ChevronDown, Plus, X } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { ORDER_STATUS_LABELS } from "@/constants/status";
import { PRODUCT_TYPE_LABELS } from "@/constants/product";
import type {
  DataExportColumn,
  DataExportSortDirection,
  OrderStatus,
  ProductType,
} from "@/types/api";

export interface DataExportFilterValues {
  search: string;
  status: OrderStatus | null;
  productType: ProductType | null;
  orderedRange: DateRange | undefined;
  shippingRange: DateRange | undefined;
}

type FilterKey = keyof DataExportFilterValues;

const FILTER_LABELS: Record<FilterKey, string> = {
  status: "ステータス",
  orderedRange: "受注日",
  productType: "商品種類",
  shippingRange: "配送予定日",
  search: "キーワード",
};

/** 最初から（値が空でも）並べておく条件。よく使うものだけ。 */
const PINNED_FILTERS: FilterKey[] = ["status", "orderedRange"];
/** 「＋ 条件を追加」から足す条件。 */
const OPTIONAL_FILTERS: FilterKey[] = ["productType", "shippingRange", "search"];

const DEFAULT_SORT = "default";

const statusOptions = Object.entries(ORDER_STATUS_LABELS) as [OrderStatus, string][];
const productTypeOptions = Object.entries(PRODUCT_TYPE_LABELS) as [ProductType, string][];

function isFilterActive(values: DataExportFilterValues, key: FilterKey): boolean {
  const value = values[key];
  if (key === "search") return (value as string).trim() !== "";
  return value !== null && value !== undefined;
}

export function hasActiveFilters(values: DataExportFilterValues): boolean {
  return (Object.keys(FILTER_LABELS) as FilterKey[]).some((k) => isFilterActive(values, k));
}

function formatRange(range: DateRange | undefined): string | null {
  if (!range?.from) return null;
  const from = format(range.from, "yyyy/MM/dd");
  return range.to ? `${from} 〜 ${format(range.to, "yyyy/MM/dd")}` : `${from} 〜`;
}

function filterValueLabel(values: DataExportFilterValues, key: FilterKey): string | null {
  switch (key) {
    case "status":
      return values.status ? ORDER_STATUS_LABELS[values.status] : null;
    case "productType":
      return values.productType ? PRODUCT_TYPE_LABELS[values.productType] : null;
    case "orderedRange":
      return formatRange(values.orderedRange);
    case "shippingRange":
      return formatRange(values.shippingRange);
    case "search":
      return values.search.trim() === "" ? null : `「${values.search.trim()}」`;
  }
}

interface FilterBarProps {
  values: DataExportFilterValues;
  onChange: (patch: Partial<DataExportFilterValues>) => void;
  columns: DataExportColumn[];
  sortColumn: string | null;
  sortDirection: DataExportSortDirection;
  onSortChange: (column: string | null, direction: DataExportSortDirection) => void;
}

/**
 * プレビュー表の上に置く条件チップ。
 *
 * 「この表に条件をかける」形にして、絞り込みと出力内容のつながりを見えるようにする。
 * よく使う条件（ステータス・受注日）は値が空でも最初から並べ、残りは「＋ 条件を追加」から足す。
 */
export function FilterBar({
  values,
  onChange,
  columns,
  sortColumn,
  sortDirection,
  onSortChange,
}: FilterBarProps) {
  // 「＋ 条件を追加」で足した条件（値を入れる前でもチップを出しておく）
  const [addedFilters, setAddedFilters] = useState<FilterKey[]>([]);
  const [openFilter, setOpenFilter] = useState<FilterKey | null>(null);
  // メニューで選んだ条件。メニューが閉じきってから（フォーカスが戻る処理を止めて）開く
  const pendingOpen = useRef<FilterKey | null>(null);

  const visibleFilters = [
    ...PINNED_FILTERS,
    ...OPTIONAL_FILTERS.filter((k) => addedFilters.includes(k) || isFilterActive(values, k)),
  ];
  const addableFilters = OPTIONAL_FILTERS.filter((k) => !visibleFilters.includes(k));

  const clearFilter = (key: FilterKey) => {
    onChange({ [key]: key === "search" ? "" : key.endsWith("Range") ? undefined : null });
    setAddedFilters((prev) => prev.filter((k) => k !== key));
  };

  const clearAll = () => {
    onChange({
      search: "",
      status: null,
      productType: null,
      orderedRange: undefined,
      shippingRange: undefined,
    });
    setAddedFilters([]);
  };

  const sortLabel = sortColumn
    ? `${columns.find((c) => c.key === sortColumn)?.label ?? sortColumn}（${
        sortDirection === "asc" ? "昇順" : "降順"
      }）`
    : "受注日時の新しい順";

  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="絞り込み条件">
      {visibleFilters.map((key) => {
        const active = isFilterActive(values, key);
        const pinned = PINNED_FILTERS.includes(key);
        return (
          <Popover
            key={key}
            open={openFilter === key}
            onOpenChange={(open) => {
              setOpenFilter(open ? key : null);
              // 足したが値を入れずに閉じた条件はチップごと引っ込める
              if (!open && !pinned && !isFilterActive(values, key)) {
                setAddedFilters((prev) => prev.filter((k) => k !== key));
              }
            }}
          >
            <div
              className={cn(
                "inline-flex h-7 items-center rounded-full border text-xs transition-colors",
                active
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-dashed text-muted-foreground hover:border-solid hover:bg-muted/60"
              )}
            >
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className={cn("flex h-full items-center gap-1 pl-2.5", active ? "pr-1" : "pr-2")}
                  aria-label={`${FILTER_LABELS[key]}で絞り込む`}
                >
                  <span className={active ? "" : "text-foreground/80"}>{FILTER_LABELS[key]}:</span>
                  <span className={active ? "font-medium" : ""}>
                    {filterValueLabel(values, key) ?? "すべて"}
                  </span>
                  {!active && <ChevronDown className="h-3 w-3" />}
                </button>
              </PopoverTrigger>
              {active && (
                <button
                  type="button"
                  onClick={() => clearFilter(key)}
                  className="mr-1 rounded-full p-0.5 hover:bg-primary/15"
                  aria-label={`${FILTER_LABELS[key]}の条件を外す`}
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
            <PopoverContent align="start" className="w-auto p-0">
              <FilterEditor
                filterKey={key}
                values={values}
                onChange={onChange}
                onDone={() => setOpenFilter(null)}
              />
            </PopoverContent>
          </Popover>
        );
      })}

      {addableFilters.length > 0 && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="inline-flex h-7 items-center gap-1 rounded-full px-2.5 text-xs text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            >
              <Plus className="h-3.5 w-3.5" />
              条件を追加
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="start"
            onCloseAutoFocus={(e) => {
              const key = pendingOpen.current;
              if (key === null) return;
              // 既定ではメニューのボタンにフォーカスが戻り、開いたポップオーバーが閉じてしまう
              e.preventDefault();
              pendingOpen.current = null;
              setOpenFilter(key);
            }}
          >
            {addableFilters.map((key) => (
              <DropdownMenuItem
                key={key}
                onSelect={() => {
                  setAddedFilters((prev) => [...prev, key]);
                  pendingOpen.current = key;
                }}
              >
                {FILTER_LABELS[key]}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      {hasActiveFilters(values) && (
        <button
          type="button"
          onClick={clearAll}
          className="h-7 rounded-full px-2 text-xs text-muted-foreground underline-offset-2 hover:underline"
        >
          条件をクリア
        </button>
      )}

      <div className="mx-1 h-4 w-px bg-border" aria-hidden />

      <Popover>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              "inline-flex h-7 items-center gap-1 rounded-full border px-2.5 text-xs",
              sortColumn
                ? "border-primary/40 bg-primary/10 text-primary"
                : "text-muted-foreground hover:bg-muted/60"
            )}
            aria-label="並び順を変える"
          >
            <ArrowDownUp className="h-3 w-3" />
            並び順: <span className={sortColumn ? "font-medium" : ""}>{sortLabel}</span>
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-[300px] space-y-2 p-3">
          <p className="text-xs text-muted-foreground">
            表の見出しをクリックしても並べ替えられます
          </p>
          <Select
            value={sortColumn ?? DEFAULT_SORT}
            onValueChange={(value) =>
              onSortChange(value === DEFAULT_SORT ? null : value, sortDirection)
            }
          >
            <SelectTrigger className="h-8 w-full text-xs" aria-label="並べ替えの項目">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={DEFAULT_SORT}>指定なし（受注日時の新しい順）</SelectItem>
              {columns.map((column) => (
                <SelectItem key={column.key} value={column.key}>
                  {column.group}：{column.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="flex gap-1">
            {(["asc", "desc"] as const).map((direction) => (
              <Button
                key={direction}
                variant={sortDirection === direction ? "secondary" : "ghost"}
                size="sm"
                className="h-7 flex-1 text-xs"
                disabled={sortColumn === null}
                onClick={() => onSortChange(sortColumn, direction)}
              >
                {direction === "asc" ? "昇順" : "降順"}
              </Button>
            ))}
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}

interface FilterEditorProps {
  filterKey: FilterKey;
  values: DataExportFilterValues;
  onChange: (patch: Partial<DataExportFilterValues>) => void;
  onDone: () => void;
}

/** チップを押したときに出る、条件 1 つを編集する中身。 */
function FilterEditor({ filterKey, values, onChange, onDone }: FilterEditorProps) {
  switch (filterKey) {
    case "status":
      return (
        <OptionList
          options={statusOptions}
          value={values.status}
          onSelect={(status) => {
            onChange({ status });
            onDone();
          }}
          allLabel="すべてのステータス"
        />
      );
    case "productType":
      return (
        <OptionList
          options={productTypeOptions}
          value={values.productType}
          onSelect={(productType) => {
            onChange({ productType });
            onDone();
          }}
          allLabel="すべての商品種類"
        />
      );
    case "orderedRange":
    case "shippingRange":
      return (
        <RangeEditor
          value={values[filterKey]}
          onApply={(range) => {
            onChange({ [filterKey]: range });
            onDone();
          }}
        />
      );
    case "search":
      return <SearchEditor value={values.search} onChange={(search) => onChange({ search })} onDone={onDone} />;
  }
}

function OptionList<T extends string>({
  options,
  value,
  onSelect,
  allLabel,
}: {
  options: [T, string][];
  value: T | null;
  onSelect: (value: T | null) => void;
  allLabel: string;
}) {
  const items: [T | null, string][] = [[null, allLabel], ...options];
  return (
    <ul className="min-w-[200px] p-1" role="listbox">
      {items.map(([optionValue, label]) => {
        const selected = optionValue === value;
        return (
          <li key={optionValue ?? "all"}>
            <button
              type="button"
              role="option"
              aria-selected={selected}
              onClick={() => onSelect(optionValue)}
              className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-muted"
            >
              <Check className={cn("h-3.5 w-3.5", selected ? "opacity-100" : "opacity-0")} />
              {label}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function RangeEditor({
  value,
  onApply,
}: {
  value: DateRange | undefined;
  onApply: (range: DateRange | undefined) => void;
}) {
  // ポップオーバーを開くたびに作り直されるので、開いた時点の値から始まる
  const [temp, setTemp] = useState<DateRange | undefined>(value);
  return (
    <div>
      <Calendar
        mode="range"
        defaultMonth={temp?.from}
        selected={temp}
        onSelect={setTemp}
        numberOfMonths={2}
      />
      <div className="flex items-center justify-between gap-2 border-t p-3">
        <span className="text-xs text-muted-foreground">
          {formatRange(temp) ?? "開始日と終了日を選んでください"}
        </span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => onApply(undefined)}>
            クリア
          </Button>
          <Button size="sm" onClick={() => onApply(temp)} disabled={!temp?.from}>
            適用
          </Button>
        </div>
      </div>
    </div>
  );
}

function SearchEditor({
  value,
  onChange,
  onDone,
}: {
  value: string;
  onChange: (value: string) => void;
  onDone: () => void;
}) {
  return (
    <div className="w-[280px] space-y-1.5 p-3">
      <Input
        autoFocus
        placeholder="注文番号、購入者名"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") onDone();
        }}
        className="h-8"
        aria-label="キーワード"
      />
      <p className="text-xs text-muted-foreground">注文番号・購入者名の一部で絞り込みます</p>
    </div>
  );
}
