/**
 * Unit tests for FEAT-0021: Display product information per OrderItem in shipment detail.
 *
 * Covers:
 * - AC-007: Section title shows "含まれる商品 (N件)"
 * - AC-008: Table header includes "数量" column
 * - AC-009: Table header includes "画像" column
 * - AC-010: thumbnail_image_url present -> img tag and download link displayed
 * - AC-011: thumbnail_image_url null -> "-" fallback displayed
 *
 * NOTE: TDD Red phase - tests should fail until implementation is completed.
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
    estimated_shipping_date: null,
    items: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

/**
 * Helper: Get the items table element (the table inside the "含まれる商品" card).
 */
function getItemsTable(): HTMLElement {
  const tables = document.querySelectorAll('table')
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

/**
 * Helper: Get table header texts from the items table.
 */
function getHeaderTexts(): string[] {
  const table = getItemsTable()
  const thead = table.querySelector('thead')
  if (!thead) {
    throw new Error('Could not find thead in items table')
  }
  const ths = thead.querySelectorAll('th')
  return Array.from(ths).map((th) => th.textContent || '')
}

// ======================================
// AC-007: Section title shows "含まれる商品 (N件)"
// ======================================

describe('AC-007: Section title shows "含まれる商品 (N件)"', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays "含まれる商品 (3件)" when items has 3 entries', () => {
    // Given: 配送詳細コンポーネントに items が3件ある shipment データを渡す
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
        {
          id: 'item-002',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品B',
          quantity: 2,
          thumbnail_image_url: null,
        },
        {
          id: 'item-003',
          order_id: 'order-002',
          order_number: 'ORD-002',
          product_name: '商品C',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: 「含まれる商品 (3件)」というテキストが表示される
    expect(screen.getByText(/含まれる商品\s*\(3件\)/)).toBeInTheDocument()
  })

  it('displays "含まれる商品 (0件)" when items is empty', () => {
    const shipment = createMockShipment({
      items: [],
    })

    render(<ShipmentDetail shipment={shipment} />)

    expect(screen.getByText(/含まれる商品\s*\(0件\)/)).toBeInTheDocument()
  })

  it('does NOT display "含まれる注文"', () => {
    // Given: 配送詳細コンポーネントに items が1件ある shipment データを渡す
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: 「含まれる注文」は表示されない
    expect(screen.queryByText(/含まれる注文/)).not.toBeInTheDocument()
  })
})

// ======================================
// AC-008: Table header includes "数量" column
// ======================================

describe('AC-008: Table header includes "数量" column', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('has "数量" in the table header', () => {
    // Given: 配送詳細コンポーネントをレンダリングする
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: テーブルヘッダーに「数量」列が存在する
    const headerTexts = getHeaderTexts()
    expect(headerTexts).toContain('数量')
  })

  it('has all expected headers: 注文番号, 商品名, 数量, 画像', () => {
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    render(<ShipmentDetail shipment={shipment} />)

    const headerTexts = getHeaderTexts()
    expect(headerTexts).toContain('注文番号')
    expect(headerTexts).toContain('商品名')
    expect(headerTexts).toContain('数量')
    expect(headerTexts).toContain('画像')
  })
})

// ======================================
// AC-009: Table header includes "画像" column
// ======================================

describe('AC-009: Table header includes "画像" column', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('has "画像" in the table header', () => {
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    render(<ShipmentDetail shipment={shipment} />)

    const headerTexts = getHeaderTexts()
    expect(headerTexts).toContain('画像')
  })
})

// ======================================
// AC-010: thumbnail_image_url present -> img + download link
// ======================================

describe('AC-010: Thumbnail image and download link displayed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays img element when thumbnail_image_url is provided', () => {
    // Given: thumbnail_image_url="https://example.com/thumb.jpg" の ShipmentItem
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: 'https://example.com/thumb.jpg',
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: img 要素が表示される
    const dataRows = getDataRows()
    expect(dataRows.length).toBe(1)

    const img = dataRows[0].querySelector('img')
    expect(img).not.toBeNull()
    expect(img?.getAttribute('src')).toBe('https://example.com/thumb.jpg')
  })

  it('displays a download button when thumbnail_image_url is provided', () => {
    // Given: thumbnail_image_url がある ShipmentItem
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: 'https://example.com/thumb.jpg',
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: ダウンロードボタンが表示される (button 要素でJavaScriptダウンロード)
    const dataRows = getDataRows()
    // 実装はbutton要素を使用してJavaScriptでダウンロードを行う
    const downloadButton = dataRows[0].querySelector('button')
    expect(downloadButton).not.toBeNull()
    // Download アイコン (SVG) が含まれていることを確認
    const downloadIcon = downloadButton?.querySelector('svg')
    expect(downloadIcon).not.toBeNull()
  })

  it('displays both img and download link for multiple items with thumbnails', () => {
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: 'https://example.com/a.jpg',
        },
        {
          id: 'item-002',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品B',
          quantity: 2,
          thumbnail_image_url: 'https://example.com/b.jpg',
        },
      ],
    })

    render(<ShipmentDetail shipment={shipment} />)

    const dataRows = getDataRows()
    expect(dataRows.length).toBe(2)

    // Both rows should have img elements
    const img1 = dataRows[0].querySelector('img')
    expect(img1?.getAttribute('src')).toBe('https://example.com/a.jpg')

    const img2 = dataRows[1].querySelector('img')
    expect(img2?.getAttribute('src')).toBe('https://example.com/b.jpg')
  })
})

// ======================================
// AC-011: thumbnail_image_url null -> "-" fallback
// ======================================

describe('AC-011: Null thumbnail_image_url shows "-" fallback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays "-" when thumbnail_image_url is null', () => {
    // Given: thumbnail_image_url=null の ShipmentItem
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: 画像セルに「-」が表示される
    const dataRows = getDataRows()
    expect(dataRows.length).toBe(1)

    // The image column is the last column (index 3: 注文番号, 商品名, 数量, 画像)
    const cells = dataRows[0].querySelectorAll('td')
    const imageCell = cells[3] // 0=注文番号, 1=商品名, 2=数量, 3=画像
    expect(imageCell).toBeDefined()
    expect(imageCell.textContent).toBe('-')
  })

  it('does not render img element when thumbnail_image_url is null', () => {
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: null,
        },
      ],
    })

    render(<ShipmentDetail shipment={shipment} />)

    const dataRows = getDataRows()
    const img = dataRows[0].querySelector('img')
    expect(img).toBeNull()
  })

  it('shows "-" for null and image for non-null in same table', () => {
    // Given: 一部の items は thumbnail_image_url があり、一部は null
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 1,
          thumbnail_image_url: 'https://example.com/a.jpg',
        },
        {
          id: 'item-002',
          order_id: 'order-002',
          order_number: 'ORD-002',
          product_name: '商品B',
          quantity: 2,
          thumbnail_image_url: null,
        },
      ],
    })

    render(<ShipmentDetail shipment={shipment} />)

    const dataRows = getDataRows()
    expect(dataRows.length).toBe(2)

    // First row: has image
    const firstRowImg = dataRows[0].querySelector('img')
    expect(firstRowImg).not.toBeNull()

    // Second row: no image, shows "-"
    const secondRowCells = dataRows[1].querySelectorAll('td')
    const secondRowImageCell = secondRowCells[3]
    expect(secondRowImageCell.textContent).toBe('-')
    expect(dataRows[1].querySelector('img')).toBeNull()
  })
})

// ======================================
// Additional: Quantity display in table rows
// ======================================

describe('Quantity display in table rows', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays the quantity value in the row', () => {
    // Given: quantity=3 の ShipmentItem
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: 3,
          thumbnail_image_url: null,
        },
      ],
    })

    // When: コンポーネントをレンダリングする
    render(<ShipmentDetail shipment={shipment} />)

    // Then: テーブル行の数量セルに「3」が表示される
    const dataRows = getDataRows()
    const cells = dataRows[0].querySelectorAll('td')
    const quantityCell = cells[2] // 0=注文番号, 1=商品名, 2=数量
    expect(quantityCell.textContent).toBe('3')
  })

  it('displays "-" when quantity is null', () => {
    const shipment = createMockShipment({
      items: [
        {
          id: 'item-001',
          order_id: 'order-001',
          order_number: 'ORD-001',
          product_name: '商品A',
          quantity: null,
          thumbnail_image_url: null,
        },
      ],
    })

    render(<ShipmentDetail shipment={shipment} />)

    const dataRows = getDataRows()
    const cells = dataRows[0].querySelectorAll('td')
    const quantityCell = cells[2]
    expect(quantityCell.textContent).toBe('-')
  })
})
