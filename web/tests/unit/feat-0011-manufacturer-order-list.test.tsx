/**
 * Unit tests for FEAT-0011: Manufacturer order list status display & filter.
 *
 * Covers:
 * - AC-007: 発注一覧のステータスカラムにStatusBadgeで実際のステータスが表示される
 * - AC-008: 発注一覧ページにステータスフィルターが表示される
 * - AC-009: ステータスフィルターで「発注済み」を選択するとフィルタリングされる
 * - AC-010: ステータスフィルターで「全て」を選択すると全メーカーが表示される
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

// Mock SWR
vi.mock('swr', () => ({
  default: vi.fn(),
}))

// Mock the hooks
vi.mock('@/features/purchase-orders/hooks/use-manufacturer-orders', () => ({
  useManufacturerOrderSummary: vi.fn(),
}))

import { ManufacturerOrderList } from '@/features/purchase-orders/components/manufacturer-order-list'
import type { ManufacturerOrderSummary } from '@/types/api'

// ======================================
// Test data factory
// ======================================

const createMockManufacturer = (overrides: Partial<ManufacturerOrderSummary> = {}): ManufacturerOrderSummary => ({
  id: 'mfr-1',
  name: 'Test Manufacturer',
  email: 'test@mfr.com',
  phone: '03-1234-5678',
  ordered_item_count: 10,
  total_quantity: 50,
  total_amount: 100000,
  lead_time_days: 7,
  is_active: true,
  ...overrides,
})

// ======================================
// AC-007: ステータスカラムにStatusBadgeで実際のステータスが表示される
// ======================================

describe('AC-007: Manufacturer order list shows dynamic status with StatusBadge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders StatusBadge for each manufacturer status instead of hardcoded Badge', () => {
    // After implementation, ManufacturerOrderSummary should have a `status` field
    // and the list should use StatusBadge instead of a hardcoded "発注済み" Badge
    const manufacturers: ManufacturerOrderSummary[] = [
      createMockManufacturer({
        id: 'mfr-1',
        name: 'Manufacturer A',
        // After type change, status field should exist
        status: 'ordered' as never,
      }),
      createMockManufacturer({
        id: 'mfr-2',
        name: 'Manufacturer B',
        status: 'manufacturing' as never,
      }),
      createMockManufacturer({
        id: 'mfr-3',
        name: 'Manufacturer C',
        status: 'delivered' as never,
      }),
    ]

    render(
      <ManufacturerOrderList
        manufacturers={manufacturers}
        onRowClick={vi.fn()}
      />
    )

    // After implementation, StatusBadge should show "発注済み", "製造中", "納品済み" based on status field
    // Currently all show "発注済み" as hardcoded Badge
    expect(screen.getByText('発注済み')).toBeInTheDocument()
    expect(screen.getByText('製造中')).toBeInTheDocument()
    expect(screen.getByText('納品済み')).toBeInTheDocument()
  })

  it('does not show all manufacturers as "発注済み" when statuses differ', () => {
    const manufacturers: ManufacturerOrderSummary[] = [
      createMockManufacturer({
        id: 'mfr-1',
        name: 'Manufacturer A',
        status: 'ordered' as never,
      }),
      createMockManufacturer({
        id: 'mfr-2',
        name: 'Manufacturer B',
        status: 'manufacturing' as never,
      }),
    ]

    render(
      <ManufacturerOrderList
        manufacturers={manufacturers}
        onRowClick={vi.fn()}
      />
    )

    // Count how many "発注済み" badges exist - should be exactly 1 (not all rows)
    const allBadges = screen.getAllByText('発注済み')
    expect(allBadges).toHaveLength(1)
  })
})

// ======================================
// AC-008: ステータスフィルターが表示される
// ======================================

describe('AC-008: Status filter is displayed on purchase orders page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a status filter select on the purchase orders page', async () => {
    const { useManufacturerOrderSummary } = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )
    const mockHook = vi.mocked(useManufacturerOrderSummary)
    mockHook.mockReturnValue({
      manufacturers: [],
      total: 0,
      page: 1,
      limit: 20,
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    })

    const { default: PurchaseOrdersPage } = await import(
      '@/app/(dashboard)/purchase-orders/page'
    )

    render(<PurchaseOrdersPage />)

    // After implementation, there should be a status filter select
    // Look for a select/combobox with status options
    const statusFilter = screen.getByRole('combobox')
    expect(statusFilter).toBeInTheDocument()
  })

  it('shows status options: 全てのステータス, 発注済み, 製造中, 納品済み', async () => {
    const user = userEvent.setup()

    const { useManufacturerOrderSummary } = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )
    const mockHook = vi.mocked(useManufacturerOrderSummary)
    mockHook.mockReturnValue({
      manufacturers: [],
      total: 0,
      page: 1,
      limit: 20,
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    })

    const { default: PurchaseOrdersPage } = await import(
      '@/app/(dashboard)/purchase-orders/page'
    )

    render(<PurchaseOrdersPage />)

    // Open the select dropdown
    const statusFilter = screen.getByRole('combobox')
    await user.click(statusFilter)

    // Should have these options
    expect(screen.getByRole('option', { name: /全て/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /発注済み/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /製造中/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /納品済み/ })).toBeInTheDocument()
  })
})

// ======================================
// AC-009: ステータスフィルターで「発注済み」を選択するとフィルタリングされる
// ======================================

describe('AC-009: Filtering by "発注済み" status shows only matching manufacturers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows only "発注済み" manufacturers when that status is selected', async () => {
    const user = userEvent.setup()

    const { useManufacturerOrderSummary } = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )
    const mockHook = vi.mocked(useManufacturerOrderSummary)
    mockHook.mockReturnValue({
      manufacturers: [
        createMockManufacturer({
          id: 'mfr-1',
          name: 'Ordered Manufacturer',
          status: 'ordered' as never,
        }),
        createMockManufacturer({
          id: 'mfr-2',
          name: 'Manufacturing Manufacturer',
          status: 'manufacturing' as never,
        }),
        createMockManufacturer({
          id: 'mfr-3',
          name: 'Delivered Manufacturer',
          status: 'delivered' as never,
        }),
      ],
      total: 3,
      page: 1,
      limit: 20,
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    })

    const { default: PurchaseOrdersPage } = await import(
      '@/app/(dashboard)/purchase-orders/page'
    )

    render(<PurchaseOrdersPage />)

    // Select "発注済み" from the filter
    const statusFilter = screen.getByRole('combobox')
    await user.click(statusFilter)
    const orderedOption = screen.getByRole('option', { name: /発注済み/ })
    await user.click(orderedOption)

    // Only "Ordered Manufacturer" should be visible
    expect(screen.getByText('Ordered Manufacturer')).toBeInTheDocument()
    expect(screen.queryByText('Manufacturing Manufacturer')).not.toBeInTheDocument()
    expect(screen.queryByText('Delivered Manufacturer')).not.toBeInTheDocument()
  })
})

// ======================================
// AC-010: 「全てのステータス」を選択すると全メーカーが表示される
// ======================================

describe('AC-010: Selecting "全て" shows all manufacturers', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows all manufacturers when "全てのステータス" is selected', async () => {
    const user = userEvent.setup()

    const { useManufacturerOrderSummary } = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )
    const mockHook = vi.mocked(useManufacturerOrderSummary)
    mockHook.mockReturnValue({
      manufacturers: [
        createMockManufacturer({
          id: 'mfr-1',
          name: 'Ordered Manufacturer',
          status: 'ordered' as never,
        }),
        createMockManufacturer({
          id: 'mfr-2',
          name: 'Manufacturing Manufacturer',
          status: 'manufacturing' as never,
        }),
        createMockManufacturer({
          id: 'mfr-3',
          name: 'Delivered Manufacturer',
          status: 'delivered' as never,
        }),
      ],
      total: 3,
      page: 1,
      limit: 20,
      isLoading: false,
      error: null,
      mutate: vi.fn(),
    })

    const { default: PurchaseOrdersPage } = await import(
      '@/app/(dashboard)/purchase-orders/page'
    )

    render(<PurchaseOrdersPage />)

    // First select a specific status to narrow down
    const statusFilter = screen.getByRole('combobox')
    await user.click(statusFilter)
    const orderedOption = screen.getByRole('option', { name: /発注済み/ })
    await user.click(orderedOption)

    // Then select "全てのステータス" to show all
    await user.click(statusFilter)
    const allOption = screen.getByRole('option', { name: /全て/ })
    await user.click(allOption)

    // All manufacturers should be visible
    expect(screen.getByText('Ordered Manufacturer')).toBeInTheDocument()
    expect(screen.getByText('Manufacturing Manufacturer')).toBeInTheDocument()
    expect(screen.getByText('Delivered Manufacturer')).toBeInTheDocument()
  })
})
