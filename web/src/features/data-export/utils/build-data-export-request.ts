import { format } from "date-fns";
import type { DateRange } from "react-day-picker";
import type {
  DataExportColumn,
  DataExportCsvRequest,
  DataExportSortDirection,
  OrderStatus,
  ProductType,
} from "@/types/api";

export interface DataExportFormState {
  selectedKeys: ReadonlySet<string>;
  search: string;
  status: OrderStatus | null;
  productType: ProductType | null;
  orderedRange: DateRange | undefined;
  shippingRange: DateRange | undefined;
  sortColumn: string | null;
  sortDirection: DataExportSortDirection;
}

function toDate(value: Date | undefined): string | null {
  return value ? format(value, "yyyy-MM-dd") : null;
}

/**
 * 画面の状態から出力リクエストを組み立てる。
 *
 * 列の順は項目一覧（API が返す順）に従う。チェックした順ではない。
 * 範囲の終了日が未指定（開始日だけ選んだ）のときは、開始日以降で絞る。
 */
export function buildDataExportRequest(
  columns: readonly DataExportColumn[],
  state: DataExportFormState
): DataExportCsvRequest {
  const search = state.search.trim();
  return {
    columns: columns.filter((c) => state.selectedKeys.has(c.key)).map((c) => c.key),
    filters: {
      status: state.status,
      product_type: state.productType,
      ordered_from: toDate(state.orderedRange?.from),
      ordered_to: toDate(state.orderedRange?.to),
      shipping_from: toDate(state.shippingRange?.from),
      shipping_to: toDate(state.shippingRange?.to),
      search: search === "" ? null : search,
    },
    sort: state.sortColumn
      ? { column: state.sortColumn, direction: state.sortDirection }
      : null,
  };
}

/** API が返す順を保ったまま、項目を分類ごとにまとめる。 */
export function groupDataExportColumns(
  columns: readonly DataExportColumn[]
): { group: string; columns: DataExportColumn[] }[] {
  const groups: { group: string; columns: DataExportColumn[] }[] = [];
  for (const column of columns) {
    const existing = groups.find((g) => g.group === column.group);
    if (existing) {
      existing.columns.push(column);
    } else {
      groups.push({ group: column.group, columns: [column] });
    }
  }
  return groups;
}

/** 出力ファイル名（データ出力_yyyyMMdd_HHmmss.csv）。 */
export function dataExportFilename(now: Date = new Date()): string {
  return `データ出力_${format(now, "yyyyMMdd_HHmmss")}.csv`;
}
