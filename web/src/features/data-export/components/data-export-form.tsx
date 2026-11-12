"use client";

import { useMemo, useState } from "react";
import { Download, Search } from "lucide-react";
import type { DateRange } from "react-day-picker";
import { toast } from "sonner";
import { downloadFileByPost } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DateRangePicker } from "@/components/common/date-range-picker";
import { ORDER_STATUS_LABELS } from "@/constants/status";
import { PRODUCT_TYPE_LABELS } from "@/constants/product";
import {
  buildDataExportRequest,
  dataExportFilename,
  groupDataExportColumns,
} from "@/features/data-export/utils/build-data-export-request";
import type {
  DataExportColumn,
  DataExportSortDirection,
  OrderStatus,
  ProductType,
} from "@/types/api";

const ALL = "all";
const DEFAULT_SORT = "default";

const statusOptions = Object.entries(ORDER_STATUS_LABELS) as [OrderStatus, string][];
const productTypeOptions = Object.entries(PRODUCT_TYPE_LABELS) as [ProductType, string][];

interface DataExportFormProps {
  columns: DataExportColumn[];
}

export function DataExportForm({ columns }: DataExportFormProps) {
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<OrderStatus | null>(null);
  const [productType, setProductType] = useState<ProductType | null>(null);
  const [orderedRange, setOrderedRange] = useState<DateRange | undefined>();
  const [shippingRange, setShippingRange] = useState<DateRange | undefined>();
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<DataExportSortDirection>("asc");
  const [isExporting, setIsExporting] = useState(false);

  const groups = useMemo(() => groupDataExportColumns(columns), [columns]);
  const selectedCount = selectedKeys.size;

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

  const handleExport = async () => {
    if (selectedCount === 0) return;
    const request = buildDataExportRequest(columns, {
      selectedKeys,
      search,
      status,
      productType,
      orderedRange,
      shippingRange,
      sortColumn,
      sortDirection,
    });
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
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>絞り込み</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            <div className="relative w-full sm:w-auto sm:min-w-[240px] sm:max-w-sm sm:flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="注文番号、購入者名で検索..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
                aria-label="キーワード"
              />
            </div>

            <Select
              value={status ?? ALL}
              onValueChange={(value) => setStatus(value === ALL ? null : (value as OrderStatus))}
            >
              <SelectTrigger className="w-full sm:w-[180px]" aria-label="受注ステータス">
                <SelectValue placeholder="受注ステータス" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>全てのステータス</SelectItem>
                {statusOptions.map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={productType ?? ALL}
              onValueChange={(value) =>
                setProductType(value === ALL ? null : (value as ProductType))
              }
            >
              <SelectTrigger className="w-full sm:w-[200px]" aria-label="商品種別">
                <SelectValue placeholder="商品種別" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>全ての商品種別</SelectItem>
                {productTypeOptions.map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <DateRangePicker
              value={orderedRange}
              onChange={setOrderedRange}
              placeholder="受注日"
              className="w-full sm:w-auto"
            />
            <DateRangePicker
              value={shippingRange}
              onChange={setShippingRange}
              placeholder="配送予定日"
              className="w-full sm:w-auto"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
          <CardTitle>出力する項目</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <span className="whitespace-nowrap text-sm text-muted-foreground">
              {selectedCount} / {columns.length} 項目を選択中
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => toggleKeys(columns.map((c) => c.key), true)}
            >
              すべて選択
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedKeys(new Set())}
              disabled={selectedCount === 0}
            >
              すべて解除
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          {groups.map(({ group, columns: groupColumns }) => {
            const keys = groupColumns.map((c) => c.key);
            const checkedInGroup = keys.filter((k) => selectedKeys.has(k)).length;
            const groupState =
              checkedInGroup === 0
                ? false
                : checkedInGroup === keys.length
                  ? true
                  : "indeterminate";
            const groupId = `group-${group}`;
            return (
              <fieldset key={group} className="space-y-3">
                <div className="flex items-center gap-2 border-b pb-2">
                  <Checkbox
                    id={groupId}
                    checked={groupState}
                    onCheckedChange={(checked) => toggleKeys(keys, checked === true)}
                    aria-label={`${group}をすべて選択`}
                  />
                  <Label htmlFor={groupId} className="font-semibold">
                    {group}
                  </Label>
                </div>
                <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-4">
                  {groupColumns.map((column) => {
                    const id = `column-${column.key}`;
                    return (
                      <div key={column.key} className="flex items-center gap-2">
                        <Checkbox
                          id={id}
                          checked={selectedKeys.has(column.key)}
                          onCheckedChange={(checked) =>
                            toggleKeys([column.key], checked === true)
                          }
                        />
                        <Label htmlFor={id} className="font-normal">
                          {column.label}
                        </Label>
                      </div>
                    );
                  })}
                </div>
              </fieldset>
            );
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>並べ替え</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4">
            <Select
              value={sortColumn ?? DEFAULT_SORT}
              onValueChange={(value) => setSortColumn(value === DEFAULT_SORT ? null : value)}
            >
              <SelectTrigger className="w-full sm:w-[280px]" aria-label="並べ替えの項目">
                <SelectValue placeholder="並べ替えの項目" />
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

            <Select
              value={sortDirection}
              onValueChange={(value) => setSortDirection(value as DataExportSortDirection)}
              disabled={sortColumn === null}
            >
              <SelectTrigger className="w-full sm:w-[140px]" aria-label="並べ替えの向き">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="asc">昇順</SelectItem>
                <SelectItem value="desc">降順</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <div className="flex flex-wrap items-center justify-end gap-4">
        {selectedCount === 0 && (
          <p className="text-sm text-muted-foreground">出力する項目を 1 つ以上選んでください</p>
        )}
        <Button onClick={handleExport} disabled={selectedCount === 0 || isExporting}>
          <Download className="mr-2 h-4 w-4" />
          {isExporting ? "出力中..." : "CSV を出力"}
        </Button>
      </div>
    </div>
  );
}
