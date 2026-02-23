/**
 * Unit tests for FEAT-0011: Shipment filter simplification.
 *
 * Covers:
 * - AC-011: 運送会社フィルターが削除されている
 * - AC-012: 作成日時ソートが削除されている
 * - AC-013: 伝票番号検索欄が削除されている
 * - AC-014: 発送日時フィルターが削除されている
 * - AC-015: 配送完了予定日時フィルターが削除されている
 * - AC-016: 検索欄とステータスフィルターは維持されている
 * - AC-017: フィルタリセットボタンが正常に動作する
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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

import { ShipmentFilters } from '@/features/shipments/components/shipment-filters'

// ======================================
// Helper: Create default props for ShipmentFilters
// After implementation, many props will be removed.
// These tests verify the AFTER state (simplified filters).
// ======================================

/**
 * After implementation, ShipmentFilters should only accept:
 * - search, status
 * - onSearchChange, onStatusChange
 * - onReset
 *
 * The following props should be REMOVED:
 * - trackingNumber, carrier, shippedFrom, shippedTo
 * - createdFrom, createdTo, deliveredFrom, deliveredTo
 * - sortBy, sortOrder
 * - onTrackingNumberChange, onCarrierChange, onShippedFromChange, onShippedToChange
 * - onCreatedFromChange, onCreatedToChange, onDeliveredFromChange, onDeliveredToChange
 * - onSortChange
 */
function createSimplifiedFilterProps() {
  return {
    search: '',
    status: null as import('@/types/api').ShipmentStatus | null,
    onSearchChange: vi.fn(),
    onStatusChange: vi.fn(),
    onReset: vi.fn(),
  }
}

// Current props (before implementation) - used to test against current code
function createCurrentFilterProps() {
  return {
    search: '',
    status: null as import('@/types/api').ShipmentStatus | null,
    trackingNumber: '',
    carrier: null as string | null,
    shippedFrom: '',
    shippedTo: '',
    createdFrom: '',
    createdTo: '',
    deliveredFrom: '',
    deliveredTo: '',
    sortBy: 'created_at' as const,
    sortOrder: 'desc' as const,
    onSearchChange: vi.fn(),
    onStatusChange: vi.fn(),
    onTrackingNumberChange: vi.fn(),
    onCarrierChange: vi.fn(),
    onShippedFromChange: vi.fn(),
    onShippedToChange: vi.fn(),
    onCreatedFromChange: vi.fn(),
    onCreatedToChange: vi.fn(),
    onDeliveredFromChange: vi.fn(),
    onDeliveredToChange: vi.fn(),
    onSortChange: vi.fn(),
    onReset: vi.fn(),
  }
}

// ======================================
// AC-011: 運送会社フィルターが削除されている
// ======================================

describe('AC-011: Carrier filter is removed from shipment filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render carrier (運送会社) select component', () => {
    // After implementation, we use simplified props
    // For now, render with current props but check carrier doesn't appear
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The carrier select should NOT be present after implementation
    // Currently it shows "全ての運送会社" as placeholder
    const carrierSelect = screen.queryByText('運送会社')
    const carrierPlaceholder = screen.queryByText('全ての運送会社')

    // After implementation, neither should exist
    expect(carrierSelect).not.toBeInTheDocument()
    expect(carrierPlaceholder).not.toBeInTheDocument()
  })
})

// ======================================
// AC-012: 作成日時ソートが削除されている
// ======================================

describe('AC-012: Sort select is removed from shipment filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render sort (並び替え) select component', () => {
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The sort select should NOT be present after implementation
    const sortPlaceholder = screen.queryByText('並び替え')
    const sortCreated = screen.queryByText(/作成日時 \(新しい順\)/)
    const sortShipped = screen.queryByText(/発送日時/)
    const sortDelivered = screen.queryByText(/配送完了予定日時/)

    expect(sortPlaceholder).not.toBeInTheDocument()
    expect(sortCreated).not.toBeInTheDocument()
    expect(sortShipped).not.toBeInTheDocument()
    expect(sortDelivered).not.toBeInTheDocument()
  })
})

// ======================================
// AC-013: 伝票番号検索欄が削除されている
// ======================================

describe('AC-013: Tracking number input is removed from shipment filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render tracking number input field', () => {
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The tracking number input should NOT be present after implementation
    const trackingInput = screen.queryByPlaceholderText('伝票番号')
    expect(trackingInput).not.toBeInTheDocument()
  })
})

// ======================================
// AC-014: 発送日時フィルターが削除されている
// ======================================

describe('AC-014: Shipped date filter is removed from shipment filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render shipped date (発送日時) range inputs', () => {
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The "発送日時" label and its date inputs should NOT be present
    const shippedLabel = screen.queryByText('発送日時')
    expect(shippedLabel).not.toBeInTheDocument()
  })
})

// ======================================
// AC-015: 配送完了予定日時フィルターが削除されている
// ======================================

describe('AC-015: Delivered date filter is removed from shipment filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render delivered date (配送完了予定日時) range inputs', () => {
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The "配送完了予定日時" label and its date inputs should NOT be present
    const deliveredLabel = screen.queryByText('配送完了予定日時')
    expect(deliveredLabel).not.toBeInTheDocument()
  })
})

// ======================================
// AC-016: 検索欄とステータスフィルターは維持されている
// ======================================

describe('AC-016: Search input and status filter are retained', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the search input field', () => {
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The search input should still be present
    const searchInput = screen.getByPlaceholderText(/検索/)
    expect(searchInput).toBeInTheDocument()
  })

  it('renders the status filter select', () => {
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // The status select should still be present
    // It shows "全てのステータス" as default
    const statusText = screen.getByText('全てのステータス')
    expect(statusText).toBeInTheDocument()
  })

  it('status filter has correct options', async () => {
    const user = userEvent.setup()
    render(<ShipmentFilters {...createCurrentFilterProps()} />)

    // Find and click the status combobox
    // After implementation, there should be only one combobox (status)
    // Currently there are multiple (status, carrier, sort)
    const comboboxes = screen.getAllByRole('combobox')
    // After implementation, there should be exactly 1 combobox (status only)
    expect(comboboxes).toHaveLength(1)
  })
})

// ======================================
// AC-017: フィルタリセットボタンが正常に動作する
// ======================================

describe('AC-017: Filter reset button works correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows reset button when search has a value', () => {
    const props = createCurrentFilterProps()
    props.search = 'test query'

    render(<ShipmentFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('shows reset button when status filter is set', () => {
    const props = createCurrentFilterProps()
    props.status = 'pending'

    render(<ShipmentFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('calls onReset when reset button is clicked', async () => {
    const user = userEvent.setup()
    const props = createCurrentFilterProps()
    props.search = 'test query'

    render(<ShipmentFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /フィルタをリセット/ })
    await user.click(resetButton)

    expect(props.onReset).toHaveBeenCalledTimes(1)
  })

  it('does not show reset button when no filters are active', () => {
    const props = createCurrentFilterProps()
    // All values are default (empty/null)

    render(<ShipmentFilters {...props} />)

    const resetButton = screen.queryByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).not.toBeInTheDocument()
  })

  it('only considers search and status for hasActiveFilters check (not removed filters)', () => {
    // After implementation, hasActiveFilters should only check search and status
    // Not the removed filters (carrier, trackingNumber, etc.)
    const props = createCurrentFilterProps()
    // Set only a removed filter value - should NOT trigger reset button
    props.search = ''
    props.status = null
    // These should be irrelevant after implementation:
    props.trackingNumber = 'some-tracking'
    props.carrier = 'yamato'

    render(<ShipmentFilters {...props} />)

    // After implementation: reset button should NOT appear because
    // search and status are both at default values
    // The removed filters should not affect hasActiveFilters
    const resetButton = screen.queryByRole('button', { name: /フィルタをリセット/ })
    expect(resetButton).not.toBeInTheDocument()
  })
})
