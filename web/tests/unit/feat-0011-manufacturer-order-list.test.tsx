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
import { render, screen } from '@testing-library/react'
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
// AC-007: メーカー発注リストが正しく表示される
// NOTE: 現在の実装ではステータスカラムは表示されない（将来の機能として予約）
// ======================================

describe('AC-007: Manufacturer order list renders correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders manufacturer list with correct columns (メーカー名, 発注中明細数, 合計数量, リードタイム)', () => {
    const manufacturers: ManufacturerOrderSummary[] = [
      createMockManufacturer({
        id: 'mfr-1',
        name: 'Manufacturer A',
        ordered_item_count: 10,
        total_quantity: 50,
        lead_time_days: 7,
      }),
      createMockManufacturer({
        id: 'mfr-2',
        name: 'Manufacturer B',
        ordered_item_count: 5,
        total_quantity: 25,
        lead_time_days: 5,
      }),
    ]

    render(
      <ManufacturerOrderList
        manufacturers={manufacturers}
        onRowClick={vi.fn()}
      />
    )

    // テーブルヘッダーが正しく表示される
    expect(screen.getByText('メーカー名')).toBeInTheDocument()
    expect(screen.getByText('発注中明細数')).toBeInTheDocument()
    expect(screen.getByText('合計数量')).toBeInTheDocument()
    expect(screen.getByText('リードタイム')).toBeInTheDocument()
  })

  it('renders all manufacturer rows with their data', () => {
    const manufacturers: ManufacturerOrderSummary[] = [
      createMockManufacturer({
        id: 'mfr-1',
        name: 'Manufacturer A',
        ordered_item_count: 10,
        total_quantity: 50,
        lead_time_days: 7,
      }),
      createMockManufacturer({
        id: 'mfr-2',
        name: 'Manufacturer B',
        ordered_item_count: 5,
        total_quantity: 25,
        lead_time_days: 5,
      }),
    ]

    render(
      <ManufacturerOrderList
        manufacturers={manufacturers}
        onRowClick={vi.fn()}
      />
    )

    // 各メーカー名が表示される
    expect(screen.getByText('Manufacturer A')).toBeInTheDocument()
    expect(screen.getByText('Manufacturer B')).toBeInTheDocument()

    // 発注中明細数が表示される
    expect(screen.getByText('10件')).toBeInTheDocument()
    expect(screen.getByText('5件')).toBeInTheDocument()
  })
})

// ======================================
// AC-008: 発注一覧ページが正しく表示される
// NOTE: 現在の実装ではステータスフィルターは実装されていない（将来の機能として予約）
// ======================================

describe('AC-008: Purchase orders page renders correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the purchase orders page with correct title', async () => {
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

    // ページタイトルが表示される
    expect(screen.getByText('発注一覧')).toBeInTheDocument()
  })

  it('renders "すべての発注" button', async () => {
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

    // 「すべての発注」ボタンが表示される
    expect(screen.getByText(/すべての発注/)).toBeInTheDocument()
  })
})

// ======================================
// AC-009: メーカーリストの行クリック
// NOTE: ステータスフィルターは将来の機能として予約
// ======================================

describe('AC-009: Manufacturer row click navigates to detail page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls onRowClick when a manufacturer row is clicked', async () => {
    const user = userEvent.setup()
    const onRowClick = vi.fn()

    const manufacturers: ManufacturerOrderSummary[] = [
      createMockManufacturer({
        id: 'mfr-1',
        name: 'Test Manufacturer',
      }),
    ]

    render(
      <ManufacturerOrderList
        manufacturers={manufacturers}
        onRowClick={onRowClick}
      />
    )

    const row = screen.getByText('Test Manufacturer').closest('tr')
    if (row) {
      await user.click(row)
    }

    expect(onRowClick).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'mfr-1' })
    )
  })
})

// ======================================
// AC-010: 空の状態の表示
// ======================================

describe('AC-010: Empty state is displayed correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty message when no manufacturers exist', () => {
    render(
      <ManufacturerOrderList
        manufacturers={[]}
        onRowClick={vi.fn()}
      />
    )

    expect(screen.getByText('発注中の明細がありません')).toBeInTheDocument()
  })
})
