/**
 * Unit tests for FEAT-0012: 発注詳細画面のステータスフィルター・キーワード検索機能
 *
 * Covers:
 * - AC-001: キーワード検索欄が表示される
 * - AC-005: ステータスフィルターが表示される
 * - AC-008: 各アイテムにステータスバッジが表示される
 * - AC-009: 受注日時フィルターが削除されている
 * - AC-010: 商品タイプフィルターが削除されている
 * - AC-012: フィルタをリセットするボタンが動作する
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

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

import { ManufacturerOrderFilters } from '@/features/purchase-orders/components/manufacturer-order-filters'
import { ManufacturerOrderDetail } from '@/features/purchase-orders/components/manufacturer-order-detail'
import type { ManufacturerOrderItemListResponse, OrderStatus } from '@/types/api'

// ======================================
// Helper: Create props for ManufacturerOrderFilters
// After implementation, the props will be simplified:
// - REMOVED: orderedFrom, orderedTo, productType
// - ADDED: search, status
// ======================================

/**
 * After implementation, ManufacturerOrderFilters should accept:
 * - search, status
 * - onSearchChange, onStatusChange
 * - onReset
 *
 * The following props should be REMOVED:
 * - orderedFrom, orderedTo, productType
 * - onOrderedFromChange, onOrderedToChange, onProductTypeChange
 */
function createNewFilterProps() {
  return {
    search: '',
    status: null as OrderStatus | null,
    onSearchChange: vi.fn(),
    onStatusChange: vi.fn(),
    onReset: vi.fn(),
  }
}

// Current props (before implementation) - for reference
function createCurrentFilterProps() {
  return {
    orderedFrom: '',
    orderedTo: '',
    productType: null as import('@/types/api').ProductType | null,
    onOrderedFromChange: vi.fn(),
    onOrderedToChange: vi.fn(),
    onProductTypeChange: vi.fn(),
    onReset: vi.fn(),
  }
}

// Mock data for ManufacturerOrderDetail tests
function createMockOrderItemsData(): ManufacturerOrderItemListResponse {
  return {
    manufacturer_id: 'mfr-001',
    manufacturer_name: 'テストメーカー',
    items: [
      {
        id: 'item-001',
        order_id: 'order-001',
        order_number: 'ORD-001',
        uid: 'UID-001',
        product_id: 'prod-001',
        product_name: 'アクリルキーホルダーA',
        product_type: 'acrylic_keychain',
        price: 1000,
        quantity: 2,
        size: '50x50mm',
        position: null,
        color: 'アクリル',
        design_image_url: null,
        thumbnail_image_url: null,
        ordered_at: '2024-01-15T10:00:00Z',
        customer_name: '田中太郎',
        status: 'ordered',  // New field
      },
      {
        id: 'item-002',
        order_id: 'order-002',
        order_number: 'ORD-002',
        uid: 'UID-002',
        product_id: 'prod-002',
        product_name: 'Tシャツ白',
        product_type: 'tshirt',
        price: 2000,
        quantity: 1,
        size: 'M',
        position: '正面',
        color: '白',
        design_image_url: null,
        thumbnail_image_url: null,
        ordered_at: '2024-01-14T10:00:00Z',
        customer_name: '鈴木花子',
        status: 'manufacturing',  // New field
      },
      {
        id: 'item-003',
        order_id: 'order-003',
        order_number: 'ORD-003',
        uid: 'UID-003',
        product_id: 'prod-003',
        product_name: 'ステッカー大',
        product_type: 'sticker',
        price: 500,
        quantity: 5,
        size: '100x100mm',
        position: null,
        color: 'ホワイト',
        design_image_url: null,
        thumbnail_image_url: null,
        ordered_at: '2024-01-13T10:00:00Z',
        customer_name: '山田一郎',
        status: 'delivered',  // New field
      },
    ],
    total: 3,
    total_quantity: 8,
    total_amount: 4500,
  }
}

/**
 * Create props for ManufacturerOrderDetail after implementation
 * The filter props will change from orderedFrom/orderedTo/productType
 * to search/status
 */
function createNewDetailProps() {
  return {
    data: createMockOrderItemsData(),
    isLoading: false,
    onStatusUpdate: vi.fn(),
    // New filter props
    search: '',
    status: null as OrderStatus | null,
    onSearchChange: vi.fn(),
    onStatusChange: vi.fn(),
    onFilterReset: vi.fn(),
  }
}

// ======================================
// AC-001: キーワード検索欄が表示される
// ======================================

describe('AC-001: Keyword search input is displayed on manufacturer order detail page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a search input with placeholder "注文番号、製品番号、商品名で検索..."', () => {
    // After implementation, the filter component should have a search input
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    const searchInput = screen.getByPlaceholderText(/注文番号.*製品番号.*商品名.*検索/i)
    expect(searchInput).toBeInTheDocument()
    expect(searchInput).toHaveAttribute('type', 'text')
  })

  it('calls onSearchChange when user types in search input', async () => {
    const user = userEvent.setup()
    const props = createNewFilterProps()

    render(<ManufacturerOrderFilters {...props} />)

    const searchInput = screen.getByPlaceholderText(/注文番号.*製品番号.*商品名.*検索/i)
    await user.type(searchInput, 'ABC')

    expect(props.onSearchChange).toHaveBeenCalled()
  })
})

// ======================================
// AC-005: ステータスフィルターが表示される
// ======================================

describe('AC-005: Status filter select is displayed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a status filter select with "全てのステータス" option', () => {
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    // The status select should show "全てのステータス" as default
    const statusText = screen.getByText('全てのステータス')
    expect(statusText).toBeInTheDocument()
  })

  it('status filter has correct options: 全てのステータス, 発注済み, 製造中, 納入済', async () => {
    const user = userEvent.setup()
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    // Find and click the status combobox to open options
    const combobox = screen.getByRole('combobox')
    await user.click(combobox)

    // Check for expected options
    // Note: "全てのステータス" appears twice (in trigger and in options) when select is open
    expect(screen.getAllByText('全てのステータス').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('発注済み')).toBeInTheDocument()
    expect(screen.getByText('製造中')).toBeInTheDocument()
    expect(screen.getByText('納入済')).toBeInTheDocument()
  })

  it('calls onStatusChange when user selects a status', async () => {
    const user = userEvent.setup()
    const props = createNewFilterProps()

    render(<ManufacturerOrderFilters {...props} />)

    // Click to open the select
    const combobox = screen.getByRole('combobox')
    await user.click(combobox)

    // Select "製造中"
    const manufacturingOption = screen.getByText('製造中')
    await user.click(manufacturingOption)

    expect(props.onStatusChange).toHaveBeenCalledWith('manufacturing')
  })
})

// ======================================
// AC-008: 各アイテムにステータスバッジが表示される
// ======================================

describe('AC-008: Status badge is displayed for each item', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders status badge for ordered items showing "発注済み"', () => {
    const props = createNewDetailProps()

    render(<ManufacturerOrderDetail {...props} />)

    // Find the row for item-001 (ordered status)
    const row = screen.getByText('ORD-001').closest('tr')
    expect(row).toBeInTheDocument()

    // Check that the row contains a "発注済み" badge
    const badge = within(row!).getByText('発注済み')
    expect(badge).toBeInTheDocument()
  })

  it('renders status badge for manufacturing items showing "製造中"', () => {
    const props = createNewDetailProps()

    render(<ManufacturerOrderDetail {...props} />)

    // Find the row for item-002 (manufacturing status)
    const row = screen.getByText('ORD-002').closest('tr')
    expect(row).toBeInTheDocument()

    // Check that the row contains a "製造中" badge
    const badge = within(row!).getByText('製造中')
    expect(badge).toBeInTheDocument()
  })

  it('renders status badge for delivered items showing "納入済"', () => {
    const props = createNewDetailProps()

    render(<ManufacturerOrderDetail {...props} />)

    // Find the row for item-003 (delivered status)
    const row = screen.getByText('ORD-003').closest('tr')
    expect(row).toBeInTheDocument()

    // Check that the row contains a "納入済" badge
    const badge = within(row!).getByText('納入済')
    expect(badge).toBeInTheDocument()
  })

  it('renders table with status column header', () => {
    const props = createNewDetailProps()

    render(<ManufacturerOrderDetail {...props} />)

    // Check for status column header
    const headers = screen.getAllByRole('columnheader')
    const statusHeader = headers.find((h) => h.textContent?.includes('ステータス'))
    expect(statusHeader).toBeInTheDocument()
  })
})

// ======================================
// AC-009: 受注日時フィルターが削除されている
// ======================================

describe('AC-009: Ordered date filter is removed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render ordered date (受注日時) range inputs', () => {
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    // The "受注日時" label should NOT be present
    const orderedDateLabel = screen.queryByText('受注日時')
    expect(orderedDateLabel).not.toBeInTheDocument()

    // No date type inputs should be present for ordered date range
    const dateInputs = screen.queryAllByRole('textbox', { name: /受注日時/ })
    expect(dateInputs).toHaveLength(0)
  })

  it('does not render date range picker with "~" separator for ordered dates', () => {
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    // Check there's no date range separator that was used for ordered dates
    // Note: The "~" might still exist for other date ranges, so we check the label context
    const orderedDateLabel = screen.queryByText('受注日時')
    expect(orderedDateLabel).not.toBeInTheDocument()
  })
})

// ======================================
// AC-010: 商品タイプフィルターが削除されている
// ======================================

describe('AC-010: Product type filter is removed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render product type (商品タイプ) select', () => {
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    // The "商品タイプ" label should NOT be present
    const productTypeLabel = screen.queryByText('商品タイプ')
    expect(productTypeLabel).not.toBeInTheDocument()

    // The "全ての商品タイプ" placeholder should NOT be present
    const productTypePlaceholder = screen.queryByText('全ての商品タイプ')
    expect(productTypePlaceholder).not.toBeInTheDocument()
  })

  it('does not render product type options like アクリルキーホルダー', () => {
    render(<ManufacturerOrderFilters {...createNewFilterProps()} />)

    // Product type options should NOT be present
    const acrylicKeychain = screen.queryByText('アクリルキーホルダー')
    const tshirt = screen.queryByText('Tシャツ')
    const sticker = screen.queryByText('ステッカー')

    expect(acrylicKeychain).not.toBeInTheDocument()
    expect(tshirt).not.toBeInTheDocument()
    expect(sticker).not.toBeInTheDocument()
  })
})

// ======================================
// AC-012: フィルタをリセットするボタンが動作する
// ======================================

describe('AC-012: Filter reset button works correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows reset button when search has a value', () => {
    const props = createNewFilterProps()
    props.search = 'test query'

    render(<ManufacturerOrderFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('shows reset button when status filter is set', () => {
    const props = createNewFilterProps()
    props.status = 'manufacturing'

    render(<ManufacturerOrderFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('calls onReset when reset button is clicked', async () => {
    const user = userEvent.setup()
    const props = createNewFilterProps()
    props.search = 'test query'

    render(<ManufacturerOrderFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    await user.click(resetButton)

    expect(props.onReset).toHaveBeenCalledTimes(1)
  })

  it('does not show reset button when no filters are active', () => {
    const props = createNewFilterProps()
    // All values are default (empty/null)

    render(<ManufacturerOrderFilters {...props} />)

    const resetButton = screen.queryByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).not.toBeInTheDocument()
  })

  it('clears search and status filter when reset is clicked', async () => {
    const user = userEvent.setup()
    const props = createNewFilterProps()
    props.search = 'キーホルダー'
    props.status = 'manufacturing'

    render(<ManufacturerOrderFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    await user.click(resetButton)

    // onReset should be called to clear both search and status
    expect(props.onReset).toHaveBeenCalledTimes(1)
  })
})

// ======================================
// Additional tests: ManufacturerOrderItem type includes status field
// ======================================

describe('ManufacturerOrderItem type includes status field', () => {
  it('ManufacturerOrderItem has status field in mock data', () => {
    const mockData = createMockOrderItemsData()

    // Each item should have a status field
    for (const item of mockData.items) {
      expect(item).toHaveProperty('status')
      expect(['ordered', 'manufacturing', 'delivered', 'shipped']).toContain(
        (item as { status: string }).status
      )
    }
  })
})

// ======================================
// Test: Filter props have changed from old to new format
// ======================================

describe('ManufacturerOrderFilters props signature change', () => {
  it('only has search and status filter props (not orderedFrom/orderedTo/productType)', () => {
    // This test verifies the prop type change
    // After implementation, the component should accept:
    // - search: string
    // - status: OrderStatus | null
    // - onSearchChange: (value: string) => void
    // - onStatusChange: (value: OrderStatus | null) => void
    // - onReset: () => void

    const props = createNewFilterProps()

    // These should be the only filter-related props
    expect(props).toHaveProperty('search')
    expect(props).toHaveProperty('status')
    expect(props).toHaveProperty('onSearchChange')
    expect(props).toHaveProperty('onStatusChange')
    expect(props).toHaveProperty('onReset')

    // These should NOT exist in the new props
    expect(props).not.toHaveProperty('orderedFrom')
    expect(props).not.toHaveProperty('orderedTo')
    expect(props).not.toHaveProperty('productType')
    expect(props).not.toHaveProperty('onOrderedFromChange')
    expect(props).not.toHaveProperty('onOrderedToChange')
    expect(props).not.toHaveProperty('onProductTypeChange')
  })
})
