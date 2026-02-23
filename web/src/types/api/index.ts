// Order types
export type OrderStatus =
  | "ordered"
  | "manufacturing"
  | "delivered"
  | "shipped";

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
  status: OrderStatus;
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
  status: "manufacturing" | "delivered";
  order_item_ids?: string[];
  note?: string;
}

// Shipment types
export type ShipmentStatus = "pending" | "ready" | "shipped";

export interface ShipmentItem {
  id: string;
  order_id: string;
  order_number: string | null;
  product_name: string | null;
}

export interface Shipment {
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

export interface ShipmentListResponse {
  items: Shipment[];
  total: number;
  page: number;
  limit: number;
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
  sharing_method: "DRIVE" | "portal";
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
