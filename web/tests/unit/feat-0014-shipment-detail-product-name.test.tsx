/**
 * Unit tests for FEAT-0014: Fix product name display in shipment detail page.
 *
 * Covers:
 * - AC-006: フロントエンドで商品名が「-」ではなく正しい値で表示される
 * - AC-007: product_name が null の場合は「-」がフォールバック表示される
 *
 * NOTE: TDD Red phase - tests should fail until implementation is completed.
 * The bug is in the backend (_to_response), but these tests verify that the
 * frontend component correctly renders whatever the API returns.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'

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

import { ShipmentDetail } from '@/features/shipments/components/shipment-detail'
import type { Shipment } from '@/types/api'

/**
 * Create a mock Shipment object for testing.
 */
function createMockShipment(overrides: Partial<Shipment> = {}): Shipment {
  return {
    id: 'shipment-001',
    status: 'pending',
    tracking_number: null,
    carrier: null,
    packing_photo_path: null,
    shipped_at: null,
    delivered_at: null,
    note: null,
    customer_name: 'Test Customer',
    customer_postal_code: '100-0001',
    customer_address_prefecture: '東京都',
    customer_address_city: '千代田区1-1-1',
    customer_address_building: null,
    customer_full_address: '東京都千代田区1-1-1',
    customer_phone: '090-1234-5678',
    items: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

/**
 * Helper: Get the items table element (the table inside the "含まれる商品" card).
 * Finds the card heading text, then traverses up to find the card container,
 * then finds the table within it.
 */
function getItemsTable(): HTMLElement {
  // The "含まれる商品" heading is inside a card.
  // We need to find the table element that is rendered as part of that card.
  const tables = document.querySelectorAll('table')
  // The items table is the last table on the page (shipment detail only has one table)
  const table = tables[tables.length - 1]
  if (!table) {
    throw new Error('Could not find items table')
  }
  return table as HTMLElement
}

/**
 * Helper: Get all data rows (non-header rows) from the items table.
 */
function getDataRows(): HTMLElement[] {
  const table = getItemsTable()
  const tbody = table.querySelector('tbody')
  if (!tbody) {
    throw new Error('Could not find tbody in items table')
  }
  return Array.from(tbody.querySelectorAll('tr')) as HTMLElement[]
}

// ======================================
// AC-006: フロントエンドで商品名が「-」ではなく正しい値で表示される
// ======================================

describe('AC-006: Product name is displayed correctly (not "-")', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays the product name "アクリルキーホルダーA" in the items table', () => {
    // Given: ShipmentResponse の items[].product_name に "アクリルキーホルダーA" が設定されている
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: 'アクリルキーホルダーA',
        },
      ],
    })

    // When: ShipmentDetail コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: テーブルに "アクリルキーホルダーA" が表示される
    expect(screen.getByText('アクリルキーホルダーA')).toBeInTheDocument()
  })

  it('does not display "-" when product_name has a valid value', () => {
    // Given: ShipmentResponse の items[].product_name に "アクリルキーホルダーA" が設定されている
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: 'アクリルキーホルダーA',
        },
      ],
    })

    // When: ShipmentDetail コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: 「-」は商品名カラムに表示されない
    const dataRows = getDataRows()
    expect(dataRows.length).toBe(1)

    // The second cell (index 1) is the product name column
    const cells = dataRows[0].querySelectorAll('td')
    const productNameCell = cells[1]
    expect(productNameCell.textContent).toBe('アクリルキーホルダーA')
    expect(productNameCell.textContent).not.toBe('-')
  })

  it('displays comma-separated product names correctly', () => {
    // Given: ShipmentResponse の items[].product_name に "商品A, 商品B" が設定されている
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A, 商品B',
        },
      ],
    })

    // When: ShipmentDetail コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: テーブルに "商品A, 商品B" が表示される
    expect(screen.getByText('商品A, 商品B')).toBeInTheDocument()
  })

  it('displays product names for multiple shipment items', () => {
    // Given: 複数の ShipmentItem にそれぞれ product_name が設定されている
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: 'アクリルキーホルダーA',
        },
        {
          id: 'item-002',
          order_id: 'order-002',
          order_number: 'ORD-002',
          product_name: 'アクリルスタンドB',
        },
      ],
    })

    // When: ShipmentDetail コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: 両方の商品名が表示される
    expect(screen.getByText('アクリルキーホルダーA')).toBeInTheDocument()
    expect(screen.getByText('アクリルスタンドB')).toBeInTheDocument()
  })
})

// ======================================
// AC-007: product_name が null の場合は「-」がフォールバック表示される
// ======================================

describe('AC-007: Null product_name shows "-" as fallback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays "-" when product_name is null', () => {
    // Given: ShipmentResponse の items[].product_name が null である
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: null,
        },
      ],
    })

    // When: ShipmentDetail コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: テーブルの商品名カラムに「-」が表示される
    const dataRows = getDataRows()
    expect(dataRows.length).toBe(1)

    const cells = dataRows[0].querySelectorAll('td')
    const productNameCell = cells[1]
    expect(productNameCell.textContent).toBe('-')
  })

  it('shows "-" for null and correct name for non-null in same table', () => {
    // Given: 一部の items は product_name があり、一部は null
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: 'アクリルキーホルダーA',
        },
        {
          id: 'item-002',
          order_id: 'order-002',
          order_number: 'ORD-002',
          product_name: null,
        },
      ],
    })

    // When: ShipmentDetail コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: 1つ目は商品名、2つ目は「-」が表示される
    const dataRows = getDataRows()
    expect(dataRows.length).toBe(2)

    // First row: product_name = "アクリルキーホルダーA"
    const firstCells = dataRows[0].querySelectorAll('td')
    expect(firstCells[1].textContent).toBe('アクリルキーホルダーA')

    // Second row: product_name = null -> "-"
    const secondCells = dataRows[1].querySelectorAll('td')
    expect(secondCells[1].textContent).toBe('-')
  })
})
