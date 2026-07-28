// Order types
export type OrderStatus =
  | "preparing_order"
  | "ordered"
  | "manufacturing"
  | "delivered"
  | "shipped"
  | "cancelled";

// OrderItemのステータス（製品単位）
// preparing_order = 発注準備中（製造データ未準備）。ordered = 発注済み（準備完了）。
// cancelled = キャンセル済み（注文のキャンセルが波及したもの）。
export type OrderItemStatus =
  | "preparing_order"
  | "ordered"
  | "manufacturing"
  | "delivered"
  | "cancelled";

// 製造データ（v2）のステータス
export type ManufacturingDataStatus = "pending" | "generating" | "ready" | "failed";

// 明細に紐づく製造データ情報（v2）
export interface MfgDataItemInfo {
  id: string;
  status: ManufacturingDataStatus;
  output_filename: string | null;
  file_size: number | null;
  error_message: string | null;
  // 元画像を管理画面から差し替えた時刻（null = 外部受注のまま）
  source_images_replaced_at?: string | null;
}

// 製造データの元画像レイヤー種別
export type SourceImageLayerType = "color" | "cutline" | "white" | "design";

// 製造データ1レイヤーの元画像（origin = 由来）
export interface SourceImageLayer {
  layer_type: SourceImageLayerType;
  origin: "external" | "uploaded";
  url: string | null;
  filename: string | null;
}

// 製造データ詳細（元画像レイヤー一覧つき）
export interface ManufacturingDataDetail extends MfgDataItemInfo {
  product_code: string;
  product_type: ProductType;
  size: string | null;
  variant: string | null;
  source_images: SourceImageLayer[];
  source_images_replaced_by: string | null;
}

export interface OrderItem {
  id: string;
  uid: string;
  product_name: string;
  product_type: ProductType;
  price: number;
  quantity: number;
  size: string | null;
  position: string | null;
  color: string | null;
  design_image_url: string | null;
  thumbnail_image_url: string | null;
  status?: OrderItemStatus;  // 製品単位のステータス
  // v2（製造データ生成）用フィールド
  product_code?: string | null;
  manufacturing_data?: MfgDataItemInfo | null;
  created_at: string;
  updated_at: string;
}

export interface ManufacturingDataInfo {
  filename: string | null;
  path: string | null;
  size: number | null;
  download_url: string | null;
}

export interface OrderShipmentInfo {
  id: string;
  status: ShipmentStatus;
  tracking_number: string | null;
  carrier: string | null;
}

export interface Order {
  id: string;
  order_number: string;
  status: OrderStatus;
  source: string | null;
  customer_name: string;
  customer_postal_code: string;
  customer_address_prefecture: string;
  customer_address_city: string;
  customer_address_building: string | null;
  customer_full_address: string;
  customer_phone: string | null;
  customer_email: string | null;
  ordered_at: string;
  total_price: number;
  estimated_shipping_date: string | null;
  items: OrderItem[];
  shipment: OrderShipmentInfo | null;
  // Legacy fields (for backward compatibility)
  product_id: string | null;
  product_name: string | null;
  price: number | null;
  quantity: number | null;
  manufacturing_data: ManufacturingDataInfo | null;
  created_at: string;
  updated_at: string;
}

export interface OrderListResponse {
  items: Order[];
  total: number;
  page: number;
  limit: number;
}

// Manufacturer Order types (メーカー発注管理)
export interface ManufacturerOrderSummary {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  ordered_item_count: number;
  total_quantity: number;
  total_amount: number;
  lead_time_days: number;
  is_active: boolean;
  status?: OrderStatus;
}

export interface ManufacturerOrderSummaryListResponse {
  items: ManufacturerOrderSummary[];
  total: number;
  page: number;
  limit: number;
}

export interface ManufacturerOrderItem {
  id: string;
  order_id: string;
  order_number: string;
  uid: string | null;
  product_id: string;
  product_name: string;
  product_type: ProductType;
  price: number;
  quantity: number;
  size: string | null;
  position: string | null;
  color: string | null;
  design_image_url: string | null;
  thumbnail_image_url: string | null;
  ordered_at: string;
  customer_name: string;
  status: OrderItemStatus;  // 製品単位のステータス
  item_status?: OrderItemStatus | null;  // 新フィールド（製品単位のステータス）
  lead_time_days: number;  // メーカーのリードタイム（日数）
  expected_delivery_date: string | null;  // 納品予定日（未設定の旧データは null）
  // 製造データ状態（v2）: null なら製造データ不要（v1）。ready 以外は発注不可。
  manufacturing_status?: ManufacturingDataStatus | null;
  // 紐づく製造データ ID（v2）。GUI からの再作成・元画像差し替えに使用。
  manufacturing_data_id?: string | null;
  // 元画像を管理画面から差し替えた時刻（null = 外部受注のまま）
  source_images_replaced_at?: string | null;
}

export interface ManufacturerOrderItemListResponse {
  manufacturer_id: string;
  manufacturer_name: string;
  items: ManufacturerOrderItem[];
  total: number;
  total_quantity: number;
  total_amount: number;
}

export interface ManufacturerOrderStatusUpdate {
  status: "ordered" | "manufacturing" | "delivered";  // 全ステータス間で遷移可能
  order_item_ids?: string[];
  note?: string;
}

// All Manufacturer Order types (全メーカー横断発注明細)
export interface AllManufacturerOrderItem {
  id: string;
  order_id: string;
  order_number: string;
  uid: string | null;
  product_id: string;
  product_name: string;
  product_type: ProductType;
  price: number;
  quantity: number;
  size: string | null;
  position: string | null;
  color: string | null;
  design_image_url: string | null;
  thumbnail_image_url: string | null;
  ordered_at: string;
  customer_name: string;
  status: OrderStatus;
  manufacturer_id: string;
  manufacturer_name: string;
  lead_time_days: number;  // メーカーのリードタイム（日数）
  expected_delivery_date: string | null;  // 納品予定日（未設定の旧データは null）
}

export interface AllManufacturerOrderItemListResponse {
  items: AllManufacturerOrderItem[];
  total: number;
  total_quantity: number;
  total_amount: number;
}

// Shipment types
export type ShipmentStatus = "pending" | "ready" | "shipped";

// Pending order status (orders without shipments)
export type PendingOrderStatus = "preparing";

// Order item summary for pending orders
export interface OrderItemSummary {
  id: string;
  product_name: string;
  product_type: ProductType;
  quantity: number;
  status: string;
  thumbnail_image_url: string | null;
}

// Pending order (order without shipment)
export interface PendingOrder {
  type: "pending_order";
  order_id: string;
  order_number: string;
  customer_name: string;
  customer_address: string;
  item_count: number;
  items_delivered: number;
  estimated_shipping_date: string | null;
  status: PendingOrderStatus;
  created_at: string;
  order_items: OrderItemSummary[];
}

export interface ShipmentItem {
  id: string;
  order_id: string;
  order_number: string | null;
  product_name: string | null;
  quantity: number | null;
  thumbnail_image_url: string | null;
}

export interface Shipment {
  type?: "shipment";  // Optional for backward compatibility
  id: string;
  status: ShipmentStatus;
  tracking_number: string | null;
  carrier: string | null;
  packing_photo_path: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  note: string | null;
  customer_name: string;
  customer_postal_code: string;
  customer_address_prefecture: string;
  customer_address_city: string;
  customer_address_building: string | null;
  customer_full_address: string;
  customer_phone: string | null;
  estimated_shipping_date: string | null;
  items: ShipmentItem[];
  created_at: string;
  updated_at: string;
}

// Union type for shipment list items (either Shipment or PendingOrder)
export type ShipmentOrPendingOrder = (Shipment & { type?: "shipment" }) | PendingOrder;

// Type guard to check if item is a PendingOrder
export function isPendingOrder(item: ShipmentOrPendingOrder): item is PendingOrder {
  return item.type === "pending_order";
}

// Type guard to check if item is a Shipment
export function isShipment(item: ShipmentOrPendingOrder): item is Shipment {
  return item.type !== "pending_order";
}

export interface ShipmentListResponse {
  items: Shipment[];
  total: number;
  page: number;
  limit: number;
}

// Extended shipment list response with pending orders
export interface ShipmentListWithPendingResponse {
  items: ShipmentOrPendingOrder[];
  total: number;
  page: number;
  limit: number;
}

export interface TrackingFileImportError {
  row: number;
  order_number: string | null;
  message: string;
}

export interface TrackingFileImportRowResult {
  order_number: string;
  tracking_number: string;
  email_sent: boolean;
}

export interface TrackingFileImportResult {
  total_count: number;
  success_count: number;
  error_count: number;
  email_sent_count: number;
  email_failed_count: number;
  errors: TrackingFileImportError[];
  results: TrackingFileImportRowResult[];
  updated_shipments: Shipment[];
}

// Manufacturer types
export interface Manufacturer {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  supported_products: string[];
  unit_prices: Record<string, number>;
  lead_time_days: number;
  daily_order_limit: number;
  sharing_method: "drive" | "portal";
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ManufacturerListResponse {
  items: Manufacturer[];
  total: number;
  page: number;
  limit: number;
}

// メーカー別 通知設定（日次発注ダイジェストメール）
export interface ManufacturerNotificationSettings {
  manufacturer_id: string;
  daily_digest_enabled: boolean;
  to_emails: string[];
  cc_emails: string[];
  last_notified_at: string | null;
}

export interface ManufacturerNotificationSettingsUpdate {
  daily_digest_enabled: boolean;
  to_emails: string[];
  cc_emails: string[];
}

// Product types
export type ProductType =
  | "acrylic_keychain"
  | "acrylic_stand"
  | "sticker"
  | "tote_bag"
  | "tshirt";

export interface Product {
  id: string;
  product_type: ProductType;
  size: string | null;
  position: string | null;
  color: string | null;
  manufacturer_id: string | null;
  manufacturer_name: string | null;
  cost: number;
  lead_time_days: number;
  order_limit: number | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
  page: number;
  limit: number;
}

// Chat types
export interface ChatAttachment {
  id: string;
  filename: string;
  download_url: string | null;
  content_type: string;
  file_size: number;
}

export interface ChatMessage {
  id: string;
  sender_type: "admin" | "manufacturer";
  sender_name: string;
  content: string;
  attachments: ChatAttachment[];
  created_at: string;
}

export interface ChatMessageListResponse {
  items: ChatMessage[];
  total: number;
  page: number;
  limit: number;
}

// Dashboard types
export interface StatusCount {
  status: string;
  count: number;
}

export interface DashboardSummary {
  orders_today: number;
  shipments_today: number;
  order_status_counts: StatusCount[];
  shipment_status_counts: StatusCount[];
  ordered_count: number;
  manufacturing_count: number;
}

// Auth types
export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: "admin" | "staff";
  is_active: boolean;
}

// Invoice types
export interface InvoiceItemRequest {
  order_item_ids: string[];
}

// Manufacturer Profile types
export interface ManufacturerProfile {
  id: string;
  name: string;
  email: string;
  phone: string | null;
  postal_code: string | null;
  address: string | null;
  bank_name: string | null;
  bank_branch: string | null;
  bank_account_type: "普通" | "当座" | null;
  bank_account_number: string | null;
  bank_account_holder: string | null;
  representative_name: string | null;
  invoice_notes: string | null;
}

export interface ManufacturerProfileUpdate {
  phone?: string | null;
  postal_code?: string | null;
  address?: string | null;
  bank_name?: string | null;
  bank_branch?: string | null;
  bank_account_type?: "普通" | "当座" | null;
  bank_account_number?: string | null;
  bank_account_holder?: string | null;
  representative_name?: string | null;
  invoice_notes?: string | null;
}

// App Settings types
export interface AppSetting {
  key: string;
  value: string;
  description: string | null;
  updated_at: string;
}

export interface AppSettingListResponse {
  items: AppSetting[];
}

// Company Holiday types
export interface CompanyHoliday {
  id: string;
  date: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface CompanyHolidayListResponse {
  items: CompanyHoliday[];
}
