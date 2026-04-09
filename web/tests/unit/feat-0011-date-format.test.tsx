/**
 * Unit tests for FEAT-0011: Date format unification (YYYY/MM/DD HH:MM).
 *
 * Covers:
 * - AC-001: order-list.tsx の受注日カラムが YYYY/MM/DD HH:MM 形式
 * - AC-002: shipment-list.tsx の作成日カラムが YYYY/MM/DD HH:MM 形式
 * - AC-003: manufacturer-order-detail.tsx の受注日カラムが YYYY/MM/DD HH:MM 形式
 * - AC-004: manufacturer/page.tsx の受注日カラムが YYYY/MM/DD HH:MM 形式
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

// Mock SWR for hooks
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: null,
    error: null,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
  })),
}))

// Mock the manufacturer portal hooks
vi.mock('@/features/manufacturer-portal/hooks/use-manufacturer-orders', () => ({
  useManufacturerOrderItems: vi.fn(() => ({
    data: undefined,
    items: [],
    total: 0,
    totalQuantity: 0,
    totalAmount: 0,
    isLoading: false,
    isFiltering: false,
    error: null,
    mutate: vi.fn(),
  })),
  downloadAllOrderDocuments: vi.fn(),
}))

// Mock the invoice dialog
vi.mock('@/features/invoice', () => ({
  InvoiceDialog: () => <div data-testid="mock-invoice-dialog" />,
}))

import { OrderList } from '@/features/orders/components/order-list'
import { ShipmentList } from '@/features/shipments/components/shipment-list'
import { ManufacturerOrderDetail } from '@/features/purchase-orders/components/manufacturer-order-detail'
import type { Order, OrderStatus, Shipment, ShipmentStatus, ManufacturerOrderItemListResponse } from '@/types/api'

// ======================================
// Test data factories
// ======================================

const createMockOrder = (overrides: Partial<Order> = {}): Order => ({
  id: 'order-1',
  order_number: 'ORD-001',
  status: 'ordered' as OrderStatus,
  source: 'shopify',
  customer_name: 'Test Customer',
  customer_postal_code: '100-0001',
  customer_address_prefecture: 'Tokyo',
  customer_address_city: 'Chiyoda',
  customer_address_building: null,
  customer_full_address: 'Tokyo Chiyoda',
  estimated_shipping_date: null,
  customer_phone: '090-1234-5678',
  customer_email: 'test@example.com',
  ordered_at: '2024-01-15T14:30:00Z',
  total_price: 3000,
  items: [],
  shipment: null,
  product_id: null,
  product_name: 'Test Product',
  price: 1000,
  quantity: 3,
  manufacturing_data: null,
  created_at: '2024-01-15T14:30:00Z',
  updated_at: '2024-01-15T14:30:00Z',
  ...overrides,
})

const createMockShipment = (overrides: Partial<Shipment> = {}): Shipment => ({
  id: 'shipment-1',
  status: 'pending' as ShipmentStatus,
  tracking_number: null,
  carrier: null,
  packing_photo_path: null,
  shipped_at: null,
  delivered_at: null,
  note: null,
  customer_name: 'Test Customer',
  customer_postal_code: '100-0001',
  customer_address_prefecture: 'Tokyo',
  customer_address_city: 'Chiyoda',
  customer_address_building: null,
  customer_full_address: 'Tokyo Chiyoda',
  estimated_shipping_date: null,
  customer_phone: '090-1234-5678',
  items: [{ id: 'item-1', order_id: 'order-1', order_number: 'ORD-001', product_name: 'Product A' }],
  created_at: '2024-01-15T14:30:00Z',
  updated_at: '2024-01-15T14:30:00Z',
  ...overrides,
})

const createMockManufacturerOrderData = (): ManufacturerOrderItemListResponse => ({
  manufacturer_id: 'mfr-1',
  manufacturer_name: 'Test Manufacturer',
  items: [
    {
      id: 'item-1',
      order_id: 'order-1',
      order_number: 'ORD-001',
      uid: '0000001',
      product_id: 'prod-1',
      product_name: 'Acrylic Keychain',
      product_type: 'acrylic_keychain',
      price: 500,
      quantity: 10,
      size: null,
      position: null,
      color: null,
      design_image_url: null,
      thumbnail_image_url: null,
      ordered_at: '2024-01-15T14:30:00Z',
      customer_name: 'Customer A',
      status: 'ordered',
    },
  ],
  total: 1,
  total_quantity: 10,
  total_amount: 5000,
})

// ======================================
// Helper: Date format verification
// ======================================

/**
 * Checks that a date string includes time component (HH:MM).
 * The expected format after implementation is YYYY/MM/DD HH:MM.
 * Current format is YYYY/MM/DD (without time), so this will fail pre-implementation.
 */
function expectDateWithTime(dateText: string | null | undefined) {
  expect(dateText).toBeTruthy()
  // Should match pattern like "2024/01/15 14:30" (YYYY/MM/DD HH:MM)
  expect(dateText).toMatch(/\d{4}\/\d{2}\/\d{2}\s+\d{1,2}:\d{2}/)
}

// ======================================
// AC-001: 受注一覧の受注日カラムが YYYY/MM/DD HH:MM 形式
// ======================================

describe('AC-001: Order list date format includes time', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays ordered_at in YYYY/MM/DD HH:MM format', () => {
    const orders = [
      createMockOrder({
        id: 'order-1',
        order_number: 'ORD-001',
        ordered_at: '2024-01-15T14:30:00Z',
      }),
    ]

    render(
      <OrderList
        orders={orders}
      />
    )

    // Find the date cell - the order row should show date with time
    // Current implementation shows only date (e.g. "2024/01/15")
    // After implementation it should show "2024/01/15 23:30" (JST = UTC+9)
    const rows = screen.getAllByRole('row')
    // First row is header, second is data
    const dataRow = rows[1]
    const cells = dataRow.querySelectorAll('td')
    // Column order: order_number, source, customer_name, product_count, ordered_at, status
    const dateCell = cells[4] // 5th column (0-indexed) = 受注日
    expectDateWithTime(dateCell.textContent)
  })

  it('displays time component for multiple orders', () => {
    const orders = [
      createMockOrder({
        id: 'order-1',
        ordered_at: '2024-06-20T09:15:00Z',
      }),
      createMockOrder({
        id: 'order-2',
        order_number: 'ORD-002',
        ordered_at: '2024-12-31T23:59:00Z',
      }),
    ]

    render(
      <OrderList
        orders={orders}
      />
    )

    const rows = screen.getAllByRole('row')
    // Check both data rows have time in date
    for (let i = 1; i < rows.length; i++) {
      const cells = rows[i].querySelectorAll('td')
      const dateCell = cells[4]
      expectDateWithTime(dateCell.textContent)
    }
  })
})

// ======================================
// AC-002: 配送一覧の作成日カラムが YYYY/MM/DD HH:MM 形式
// ======================================

describe('AC-002: Shipment list date format includes time', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays created_at in YYYY/MM/DD HH:MM format', () => {
    const shipments = [
      createMockShipment({
        id: 'shipment-1',
        created_at: '2024-01-15T14:30:00Z',
      }),
    ]

    render(
      <ShipmentList
        shipments={shipments}
        selectedIds={new Set()}
        onSelectChange={vi.fn()}
      />
    )

    const rows = screen.getAllByRole('row')
    const dataRow = rows[1]
    const cells = dataRow.querySelectorAll('td')
    // Column order: checkbox, shipment_id, destination, item_count, tracking_number, created_at, status
    const dateCell = cells[5] // 6th column (0-indexed) = 作成日
    expectDateWithTime(dateCell.textContent)
  })

  it('displays time component for multiple shipments', () => {
    const shipments = [
      createMockShipment({
        id: 'shipment-1',
        created_at: '2024-03-10T08:45:00Z',
      }),
      createMockShipment({
        id: 'shipment-2',
        created_at: '2024-07-22T16:20:00Z',
      }),
    ]

    render(
      <ShipmentList
        shipments={shipments}
        selectedIds={new Set()}
        onSelectChange={vi.fn()}
      />
    )

    const rows = screen.getAllByRole('row')
    for (let i = 1; i < rows.length; i++) {
      const cells = rows[i].querySelectorAll('td')
      const dateCell = cells[5]
      expectDateWithTime(dateCell.textContent)
    }
  })
})

// ======================================
// AC-003: 発注詳細の受注日カラムが YYYY/MM/DD HH:MM 形式
// ======================================

describe('AC-003: Manufacturer order detail date format includes time', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays ordered_at in YYYY/MM/DD HH:MM format in order items table', () => {
    const data = createMockManufacturerOrderData()

    render(
      <ManufacturerOrderDetail
        data={data}
        isLoading={false}
        onStatusUpdate={vi.fn()}
        search=""
        status={null}
        onSearchChange={vi.fn()}
        onStatusChange={vi.fn()}
        onFilterReset={vi.fn()}
      />
    )

    // Find the table rows with order items
    // The order item row should show ordered_at with time
    const rows = screen.getAllByRole('row')
    // Find the row containing the order item data
    const itemRow = rows.find(row => row.textContent?.includes('ORD-001'))
    expect(itemRow).toBeTruthy()

    // The last cell in the item row should be the date
    const cells = itemRow!.querySelectorAll('td')
    const dateCell = cells[cells.length - 1] // Last column = 受注日
    expectDateWithTime(dateCell.textContent)
  })
})

// ======================================
// AC-004: メーカーポータルの受注日カラムが YYYY/MM/DD HH:MM 形式
// ======================================

describe('AC-004: Manufacturer portal date format includes time', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays ordered_at in YYYY/MM/DD HH:MM format in manufacturer portal', async () => {
    // We need to mock the hook to return items
    const { useManufacturerOrderItems } = await import(
      '@/features/manufacturer-portal/hooks/use-manufacturer-orders'
    )
    const mockHook = vi.mocked(useManufacturerOrderItems)
    mockHook.mockReturnValue({
      data: undefined,
      items: [
        {
          id: 'item-1',
          order_id: 'order-1',
          order_number: 'ORD-001',
          uid: '0000001',
          product_id: 'prod-1',
          product_name: 'Acrylic Keychain',
          product_type: 'acrylic_keychain',
          price: 500,
          quantity: 10,
          size: null,
          position: null,
          color: null,
          design_image_url: null,
          thumbnail_image_url: null,
          ordered_at: '2024-01-15T14:30:00Z',
          customer_name: 'Customer A',
          status: 'ordered',
        },
      ],
      total: 1,
      totalQuantity: 10,
      totalAmount: 5000,
      isLoading: false,
      isFiltering: false,
      error: null,
      mutate: vi.fn(),
    } as ReturnType<typeof useManufacturerOrderItems>)

    // Dynamic import to ensure mocks are set up
    const { default: ManufacturerDashboardPage } = await import(
      '@/app/(manufacturer)/manufacturer/page'
    )

    render(<ManufacturerDashboardPage />)

    // Find the order item row with the date
    const rows = screen.getAllByRole('row')
    const itemRow = rows.find(row => row.textContent?.includes('ORD-001'))
    expect(itemRow).toBeTruthy()

    // The first data cell after checkbox should be the date (注文日)
    const cells = itemRow!.querySelectorAll('td')
    // Column order: checkbox, 注文日, 注文番号, 製品番号, 商品名, 個数
    const dateCell = cells[1] // 2nd column (0-indexed) = 注文日
    expectDateWithTime(dateCell.textContent)
  })
})
