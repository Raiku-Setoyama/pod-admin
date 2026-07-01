import type {
  ManufacturingDataStatus,
  OrderStatus,
  PendingOrderStatus,
  ShipmentStatus,
} from "@/types/api";

// ========================================
// Order Status (受注ステータス)
// ========================================

/**
 * OrderStatus のラベル名（統一済み）
 */
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  ordered: "発注済み",
  manufacturing: "製造中",
  delivered: "納品済み",
  shipped: "発送完了",
};

/**
 * OrderStatus の色（Tailwind CSS クラス）
 */
export const ORDER_STATUS_COLORS: Record<OrderStatus, string> = {
  ordered: "bg-yellow-100 text-yellow-700 border-yellow-300",
  manufacturing: "bg-blue-100 text-blue-700 border-blue-300",
  delivered: "bg-purple-100 text-purple-700 border-purple-300",
  shipped: "bg-emerald-100 text-emerald-700 border-emerald-300",
};

// ========================================
// Shipment Status (配送ステータス)
// ========================================

/**
 * ShipmentStatus のラベル名（統一済み）
 */
export const SHIPMENT_STATUS_LABELS: Record<ShipmentStatus, string> = {
  pending: "配送準備中",
  ready: "配送準備完了",
  shipped: "発送完了",
};

/**
 * ShipmentStatus の色（Tailwind CSS クラス）
 */
export const SHIPMENT_STATUS_COLORS: Record<ShipmentStatus, string> = {
  pending: "bg-gray-100 text-gray-700 border-gray-300",
  ready: "bg-cyan-100 text-cyan-700 border-cyan-300",
  shipped: "bg-emerald-100 text-emerald-700 border-emerald-300",
};

// ========================================
// Pending Order Status (未配送注文ステータス)
// ========================================

/**
 * PendingOrderStatus のラベル名
 */
export const PENDING_ORDER_STATUS_LABELS: Record<PendingOrderStatus, string> = {
  preparing: "商品準備中",
};

/**
 * PendingOrderStatus の色（Tailwind CSS クラス）
 */
export const PENDING_ORDER_STATUS_COLORS: Record<PendingOrderStatus, string> = {
  preparing: "bg-orange-100 text-orange-700 border-orange-300",
};

// ========================================
// Manufacturing Data Status (製造データ生成ステータス / v2)
// ========================================

/**
 * ManufacturingDataStatus のラベル名
 *
 * 注: pending/ready は配送ステータスと値が重複するため、StatusBadge の共通ラベルとは
 * 別管理とする（意味が異なる: 生成待ち/生成完了）。
 */
export const MANUFACTURING_DATA_STATUS_LABELS: Record<ManufacturingDataStatus, string> = {
  pending: "生成待ち",
  generating: "生成中",
  ready: "生成完了",
  failed: "生成失敗",
};

/**
 * ManufacturingDataStatus の色（Tailwind CSS クラス）
 */
export const MANUFACTURING_DATA_STATUS_COLORS: Record<ManufacturingDataStatus, string> = {
  pending: "bg-gray-100 text-gray-700 border-gray-300",
  generating: "bg-blue-100 text-blue-700 border-blue-300",
  ready: "bg-emerald-100 text-emerald-700 border-emerald-300",
  failed: "bg-red-100 text-red-700 border-red-300",
};

/**
 * ManufacturingDataStatus のラベルを取得
 */
export function getManufacturingDataStatusLabel(status: ManufacturingDataStatus): string {
  return MANUFACTURING_DATA_STATUS_LABELS[status] ?? status;
}

// ========================================
// Combined Status (StatusBadge 用)
// ========================================

export type StatusType = OrderStatus | ShipmentStatus | PendingOrderStatus;

/**
 * 全ステータスのラベル名
 */
export const STATUS_LABELS: Record<StatusType, string> = {
  ...ORDER_STATUS_LABELS,
  ...SHIPMENT_STATUS_LABELS,
  ...PENDING_ORDER_STATUS_LABELS,
};

/**
 * 全ステータスの色
 */
export const STATUS_COLORS: Record<StatusType, string> = {
  ...ORDER_STATUS_COLORS,
  ...SHIPMENT_STATUS_COLORS,
  ...PENDING_ORDER_STATUS_COLORS,
};

// ========================================
// Helper functions
// ========================================

/**
 * OrderStatus のラベルを取得
 */
export function getOrderStatusLabel(status: OrderStatus): string {
  return ORDER_STATUS_LABELS[status] ?? status;
}

/**
 * ShipmentStatus のラベルを取得
 */
export function getShipmentStatusLabel(status: ShipmentStatus): string {
  return SHIPMENT_STATUS_LABELS[status] ?? status;
}

/**
 * PendingOrderStatus のラベルを取得
 */
export function getPendingOrderStatusLabel(status: PendingOrderStatus): string {
  return PENDING_ORDER_STATUS_LABELS[status] ?? status;
}

/**
 * ステータスのラベルを取得（OrderStatus / ShipmentStatus 両対応）
 */
export function getStatusLabel(status: StatusType): string {
  return STATUS_LABELS[status] ?? status;
}

/**
 * ステータスの色を取得
 */
export function getStatusColor(status: StatusType): string {
  return STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700 border-gray-300";
}

// ========================================
// Filter Options (フィルター用選択肢)
// ========================================

export interface StatusOption<T extends string> {
  value: T | "all";
  label: string;
}

/**
 * OrderStatus のフィルター選択肢（"全て" を含む）
 */
export function getOrderStatusOptions(): StatusOption<OrderStatus>[] {
  return [
    { value: "all", label: "全てのステータス" },
    ...Object.entries(ORDER_STATUS_LABELS).map(([value, label]) => ({
      value: value as OrderStatus,
      label,
    })),
  ];
}

/**
 * ShipmentStatus のフィルター選択肢（"全て" を含む）
 */
export function getShipmentStatusOptions(): StatusOption<ShipmentStatus>[] {
  return [
    { value: "all", label: "全てのステータス" },
    ...Object.entries(SHIPMENT_STATUS_LABELS).map(([value, label]) => ({
      value: value as ShipmentStatus,
      label,
    })),
  ];
}

/**
 * 配送一覧フィルター用（ShipmentStatus + PendingOrderStatus の組み合わせ）
 */
export function getShipmentListFilterOptions(): StatusOption<ShipmentStatus | PendingOrderStatus>[] {
  return [
    { value: "all", label: "全てのステータス" },
    { value: "preparing", label: PENDING_ORDER_STATUS_LABELS.preparing },
    { value: "pending", label: SHIPMENT_STATUS_LABELS.pending },
    { value: "ready", label: SHIPMENT_STATUS_LABELS.ready },
    { value: "shipped", label: SHIPMENT_STATUS_LABELS.shipped },
  ];
}

/**
 * 受注一覧フィルター用（OrderStatus + ShipmentStatus の組み合わせ）
 */
export function getOrderFilterStatusOptions(): StatusOption<OrderStatus | ShipmentStatus>[] {
  return [
    { value: "all", label: "全てのステータス" },
    { value: "ordered", label: ORDER_STATUS_LABELS.ordered },
    { value: "manufacturing", label: ORDER_STATUS_LABELS.manufacturing },
    { value: "pending", label: SHIPMENT_STATUS_LABELS.pending },
    { value: "ready", label: SHIPMENT_STATUS_LABELS.ready },
    { value: "shipped", label: ORDER_STATUS_LABELS.shipped },
  ];
}

/**
 * 発注詳細フィルター用（delivered を除いた OrderStatus）
 */
export function getManufacturerOrderFilterStatusOptions(): StatusOption<OrderStatus>[] {
  return [
    { value: "all", label: "全てのステータス" },
    { value: "ordered", label: ORDER_STATUS_LABELS.ordered },
    { value: "manufacturing", label: ORDER_STATUS_LABELS.manufacturing },
    { value: "delivered", label: ORDER_STATUS_LABELS.delivered },
  ];
}

// ========================================
// Dialog Options (ダイアログ用選択肢)
// ========================================

export interface DialogStatusOption<T extends string> {
  value: T;
  label: string;
}

/**
 * 受注ステータス更新ダイアログ用（shipped 除外）
 */
export function getOrderStatusUpdateOptions(): DialogStatusOption<OrderStatus>[] {
  return [
    { value: "ordered", label: ORDER_STATUS_LABELS.ordered },
    { value: "manufacturing", label: ORDER_STATUS_LABELS.manufacturing },
    { value: "delivered", label: ORDER_STATUS_LABELS.delivered },
  ];
}

/**
 * 発注詳細ステータス更新ダイアログ用（全ステータス間で遷移可能）
 */
export function getManufacturerOrderStatusUpdateOptions(): DialogStatusOption<"ordered" | "manufacturing" | "delivered">[] {
  return [
    { value: "ordered", label: ORDER_STATUS_LABELS.ordered },
    { value: "manufacturing", label: ORDER_STATUS_LABELS.manufacturing },
    { value: "delivered", label: ORDER_STATUS_LABELS.delivered },
  ];
}

/**
 * 配送ステータス更新ダイアログ用
 */
export function getShipmentStatusUpdateOptions(): DialogStatusOption<ShipmentStatus>[] {
  return [
    { value: "pending", label: SHIPMENT_STATUS_LABELS.pending },
    { value: "ready", label: SHIPMENT_STATUS_LABELS.ready },
    { value: "shipped", label: SHIPMENT_STATUS_LABELS.shipped },
  ];
}
