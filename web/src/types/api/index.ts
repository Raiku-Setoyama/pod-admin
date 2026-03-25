// Order types
export type OrderStatus =
  | "ordered"
  | "manufacturing"
  | "delivered"
  | "shipped";

// OrderItemのステータス（製品単位）
export type OrderItemStatus = "ordered" | "manufacturing" | "delivered";

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
  expected_delivery_date: string;  // 納品予定日
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
  expected_delivery_date: string;  // 納品予定日
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

export interface ProductAttributeSpec {
  product_type: ProductType;
  sizes: string[];
  colors: string[];
  positions: string[];
  required_size: boolean;
  required_color: boolean;
  required_position: boolean;
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
