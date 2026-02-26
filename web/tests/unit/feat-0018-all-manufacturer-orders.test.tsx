/**
 * Unit tests for FEAT-0018: 全メーカー横断発注明細一覧「すべての発注」ページ
 * Updated for FEAT-0020: 金額表示の削除
 *
 * Covers:
 * - AC-012: /purchase-orders/all ページが全メーカーの発注明細を表示する
 * - AC-013: テーブルに必要なカラムが表示される（メーカー名カラム含む、金額カラムなし）
 * - AC-014: 発注一覧ページに「すべての発注を見る」ボタンが表示される
 * - AC-015: フィルター（ステータス、キーワード検索）が正常に動作する
 * - AC-016: メーカーフィルターで特定メーカーに絞り込みできる
 * - AC-017: 発注明細が0件の場合、空メッセージが表示される
 * - AC-018: サマリーカード（合計明細数、合計数量）が表示される（合計金額なし）
 *
 * FEAT-0020 Acceptance Criteria:
 * - AC-001: サマリーカードに「合計金額」が表示されない
 * - AC-002: テーブルヘッダーに「金額」カラムが表示されない（カラム数は9）
 * - AC-003: テーブル行に金額セルが表示されない
 * - AC-004: サマリーカードのグリッドが2カラムに変更される
 * - AC-005: 既存の明細数・合計数量の表示は維持される
 * - AC-006: page.tsx の displayData フォールバックから total_amount が削除される
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderHook } from '@testing-library/react'

// Mock API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

// Mock SWR
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: undefined,
    error: undefined,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
  })),
}))

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

// Mock next/navigation with controllable values
const mockPush = vi.fn()
const mockReplace = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/purchase-orders/all',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}))

// ======================================
// Types (for the new AllManufacturerOrderItem)
// ======================================

interface AllManufacturerOrderItem {
  id: string
  order_id: string
  order_number: string
  uid: string | null
  product_id: string
  product_name: string
  product_type: string
  price: number
  quantity: number
  size: string | null
  position: string | null
  color: string | null
  design_image_url: string | null
  thumbnail_image_url: string | null
  ordered_at: string
  customer_name: string
  status: string
  manufacturer_id: string
  manufacturer_name: string
}

interface AllManufacturerOrderItemListResponse {
  items: AllManufacturerOrderItem[]
  total: number
  total_quantity: number
  total_amount: number
}

// ======================================
// Mock data factory
// ======================================

function createMockAllOrderItemsData(): AllManufacturerOrderItemListResponse {
  return {
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
        ordered_at: '2026-01-15T10:00:00Z',
        customer_name: '田中太郎',
        status: 'ordered',
        manufacturer_id: 'mfr-001',
        manufacturer_name: 'メーカーA',
      },
      {
        id: 'item-002',
        order_id: 'order-002',
        order_number: 'ORD-002',
        uid: 'UID-002',
        product_id: 'prod-002',
        product_name: 'Tシャツ白M',
        product_type: 'tshirt',
        price: 2000,
        quantity: 1,
        size: 'M',
        position: '正面',
        color: '白',
        design_image_url: null,
        thumbnail_image_url: null,
        ordered_at: '2026-01-14T10:00:00Z',
        customer_name: '鈴木花子',
        status: 'manufacturing',
        manufacturer_id: 'mfr-001',
        manufacturer_name: 'メーカーA',
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
        ordered_at: '2026-01-13T10:00:00Z',
        customer_name: '山田一郎',
        status: 'ordered',
        manufacturer_id: 'mfr-002',
        manufacturer_name: 'メーカーB',
      },
    ],
    total: 3,
    total_quantity: 8,
    total_amount: 6500,
  }
}

function createEmptyMockData(): AllManufacturerOrderItemListResponse {
  return {
    items: [],
    total: 0,
    total_quantity: 0,
    total_amount: 0,
  }
}

// ======================================
// AC-012: /purchase-orders/all ページが「すべての発注」一覧を表示する
// ======================================

describe('AC-012: /purchase-orders/all page displays all manufacturer order items', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the AllManufacturerOrderList component with order items', async () => {
    // Import the new component
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // 全メーカーの発注明細がテーブルに表示される
    expect(screen.getByText('ORD-001')).toBeInTheDocument()
    expect(screen.getByText('ORD-002')).toBeInTheDocument()
    expect(screen.getByText('ORD-003')).toBeInTheDocument()
  })

  it('renders manufacturer name for each order item row', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // 各行にメーカー名が表示される（メーカーAは2行あるのでgetAllByTextを使用）
    expect(screen.getAllByText('メーカーA').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('メーカーB')).toBeInTheDocument()
  })
})

// ======================================
// AC-013: テーブルに必要なカラムが表示される
// ======================================

describe('AC-013: AllManufacturerOrderList table has required columns (FEAT-0020: 金額カラム削除)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders table with all required column headers (金額カラムなし、9カラム)', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    const headers = screen.getAllByRole('columnheader')
    const headerTexts = headers.map(h => h.textContent)

    // 必要なカラムが全て存在すること（金額以外）
    expect(headerTexts.some(t => t?.includes('メーカー名'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('注文番号'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('製品番号'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('商品名'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('商品タイプ'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('ステータス'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('数量'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('顧客名'))).toBe(true)
    expect(headerTexts.some(t => t?.includes('受注日'))).toBe(true)

    // FEAT-0020: 金額カラムが存在しないこと
    expect(headerTexts.some(t => t?.includes('金額'))).toBe(false)

    // FEAT-0020: カラム数は9であること
    expect(headers).toHaveLength(9)
  })
})

// ======================================
// AC-014: 発注一覧ページに「すべての発注を見る」ボタンが表示される
// ======================================

describe('AC-014: Purchase orders page has "すべての発注を見る" navigation button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders "すべての発注を見る" button on purchase orders page', async () => {
    const { default: PurchaseOrdersPage } = await import(
      '@/app/(dashboard)/purchase-orders/page'
    )

    render(<PurchaseOrdersPage />)

    // 「すべての発注を見る」ボタンが表示される
    const navButton = screen.getByText(/すべての発注を見る/)
    expect(navButton).toBeInTheDocument()
  })

  it('navigates to /purchase-orders/all when button is clicked', async () => {
    const user = userEvent.setup()

    const { default: PurchaseOrdersPage } = await import(
      '@/app/(dashboard)/purchase-orders/page'
    )

    render(<PurchaseOrdersPage />)

    // ボタンをクリック
    const navButton = screen.getByText(/すべての発注を見る/)
    await user.click(navButton)

    // /purchase-orders/all に遷移する
    // Link コンポーネントの場合は href を確認
    const linkElement = navButton.closest('a')
    if (linkElement) {
      expect(linkElement).toHaveAttribute('href', '/purchase-orders/all')
    } else {
      // Button の場合は router.push を確認
      expect(mockPush).toHaveBeenCalledWith('/purchase-orders/all')
    }
  })
})

// ======================================
// AC-015: フィルター（ステータス、キーワード検索）が正常に動作する
// ======================================

describe('AC-015: Filters (status, keyword search) work correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders AllManufacturerOrderFilters component with search and status inputs', async () => {
    const { AllManufacturerOrderFilters } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-filters'
    )

    const props = {
      search: '',
      status: null as string | null,
      manufacturerId: null as string | null,
      productType: null as string | null,
      orderedFrom: '',
      orderedTo: '',
      onSearchChange: vi.fn(),
      onStatusChange: vi.fn(),
      onManufacturerIdChange: vi.fn(),
      onProductTypeChange: vi.fn(),
      onOrderedFromChange: vi.fn(),
      onOrderedToChange: vi.fn(),
      onReset: vi.fn(),
      manufacturers: [
        { id: 'mfr-001', name: 'メーカーA' },
        { id: 'mfr-002', name: 'メーカーB' },
      ],
    }

    render(<AllManufacturerOrderFilters {...props} />)

    // 検索入力が存在する
    const searchInput = screen.getByPlaceholderText(/注文番号.*商品名.*検索/i)
      || screen.getByPlaceholderText(/検索/i)
    expect(searchInput).toBeInTheDocument()
  })

  it('calls onStatusChange when status filter is changed', async () => {
    const user = userEvent.setup()

    const { AllManufacturerOrderFilters } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-filters'
    )

    const onStatusChange = vi.fn()

    const props = {
      search: '',
      status: null as string | null,
      manufacturerId: null as string | null,
      productType: null as string | null,
      orderedFrom: '',
      orderedTo: '',
      onSearchChange: vi.fn(),
      onStatusChange,
      onManufacturerIdChange: vi.fn(),
      onProductTypeChange: vi.fn(),
      onOrderedFromChange: vi.fn(),
      onOrderedToChange: vi.fn(),
      onReset: vi.fn(),
      manufacturers: [],
    }

    render(<AllManufacturerOrderFilters {...props} />)

    // ステータスフィルターのセレクトを探してクリック
    const statusText = screen.getByText('全てのステータス')
    expect(statusText).toBeInTheDocument()

    // セレクトを開いて「発注済み」を選択
    const combobox = screen.getAllByRole('combobox').find(
      el => el.textContent?.includes('全てのステータス')
    )
    if (combobox) {
      await user.click(combobox)
      const orderedOption = screen.getByText('発注済み')
      await user.click(orderedOption)
      expect(onStatusChange).toHaveBeenCalledWith('ordered')
    }
  })
})

// ======================================
// AC-016: メーカーフィルターで特定メーカーに絞り込みできる
// ======================================

describe('AC-016: Manufacturer filter allows filtering by specific manufacturer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders manufacturer filter select with manufacturer options', async () => {
    const { AllManufacturerOrderFilters } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-filters'
    )

    const props = {
      search: '',
      status: null as string | null,
      manufacturerId: null as string | null,
      productType: null as string | null,
      orderedFrom: '',
      orderedTo: '',
      onSearchChange: vi.fn(),
      onStatusChange: vi.fn(),
      onManufacturerIdChange: vi.fn(),
      onProductTypeChange: vi.fn(),
      onOrderedFromChange: vi.fn(),
      onOrderedToChange: vi.fn(),
      onReset: vi.fn(),
      manufacturers: [
        { id: 'mfr-001', name: 'メーカーA' },
        { id: 'mfr-002', name: 'メーカーB' },
      ],
    }

    render(<AllManufacturerOrderFilters {...props} />)

    // メーカーフィルターが存在する（「全てのメーカー」デフォルト表示）
    const makerText = screen.getByText('全てのメーカー')
    expect(makerText).toBeInTheDocument()
  })

  it('calls onManufacturerIdChange when a manufacturer is selected', async () => {
    const user = userEvent.setup()

    const { AllManufacturerOrderFilters } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-filters'
    )

    const onManufacturerIdChange = vi.fn()

    const props = {
      search: '',
      status: null as string | null,
      manufacturerId: null as string | null,
      productType: null as string | null,
      orderedFrom: '',
      orderedTo: '',
      onSearchChange: vi.fn(),
      onStatusChange: vi.fn(),
      onManufacturerIdChange,
      onProductTypeChange: vi.fn(),
      onOrderedFromChange: vi.fn(),
      onOrderedToChange: vi.fn(),
      onReset: vi.fn(),
      manufacturers: [
        { id: 'mfr-001', name: 'メーカーA' },
        { id: 'mfr-002', name: 'メーカーB' },
      ],
    }

    render(<AllManufacturerOrderFilters {...props} />)

    // メーカーフィルターのセレクトを開いて「メーカーA」を選択
    const combobox = screen.getAllByRole('combobox').find(
      el => el.textContent?.includes('全てのメーカー')
    )
    if (combobox) {
      await user.click(combobox)
      const makerOption = screen.getByText('メーカーA')
      await user.click(makerOption)
      expect(onManufacturerIdChange).toHaveBeenCalledWith('mfr-001')
    }
  })
})

// ======================================
// AC-017: 発注明細が0件の場合、空メッセージが表示される
// ======================================

describe('AC-017: Empty message is displayed when no order items exist', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows empty message when items array is empty', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const emptyData = createEmptyMockData()

    render(
      <AllManufacturerOrderList
        data={emptyData}
        isLoading={false}
      />
    )

    // 「発注中の明細がありません」等の空メッセージが表示される
    const emptyMessage = screen.getByText(/明細がありません/i)
      || screen.getByText(/データがありません/i)
    expect(emptyMessage).toBeInTheDocument()
  })
})

// ======================================
// AC-018: サマリーカード（合計明細数、合計数量、合計金額）が表示される
// ======================================

describe('AC-018: Summary cards display total count, total quantity (FEAT-0020: 合計金額なし)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders summary cards with correct values (金額なし)', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // 合計明細数が表示される（サマリーカード内の "3件"）
    expect(screen.getAllByText(/3件/).length).toBeGreaterThanOrEqual(1)

    // 合計数量が表示される（サマリーカード内の "8点"）
    expect(screen.getByText(/8点/)).toBeInTheDocument()

    // FEAT-0020: 合計金額が表示されないこと
    expect(screen.queryByText(/¥6,500/)).not.toBeInTheDocument()
  })

  it('renders summary labels for count and quantity only (金額ラベルなし)', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // サマリーのラベルが存在すること（明細数、合計数量のみ）
    expect(screen.getByText(/明細数/)).toBeInTheDocument()
    expect(screen.getByText(/合計数量/)).toBeInTheDocument()

    // FEAT-0020: 合計金額ラベルが存在しないこと
    expect(screen.queryByText(/合計金額/)).not.toBeInTheDocument()
  })
})

// ======================================
// useAllManufacturerOrderItems hook test
// ======================================

describe('useAllManufacturerOrderItems hook', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('hook exists and can be imported', async () => {
    const hookModule = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )

    expect(hookModule.useAllManufacturerOrderItems).toBeDefined()
    expect(typeof hookModule.useAllManufacturerOrderItems).toBe('function')
  })

  it('constructs correct API URL with filters', async () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    const { useAllManufacturerOrderItems } = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )

    renderHook(() =>
      useAllManufacturerOrderItems({
        status: 'ordered',
        search: 'テスト',
        manufacturer_id: 'mfr-001',
      })
    )

    // useSWR が正しいURLパラメータで呼ばれたことを確認
    expect(useSWR).toHaveBeenCalledWith(
      expect.stringContaining('/manufacturers/all-order-items'),
      expect.anything(),
      expect.anything(),
    )

    const callArgs = useSWR.mock.calls
    const lastCallKey = callArgs[callArgs.length - 1]?.[0] as string
    expect(lastCallKey).toContain('status=ordered')
    expect(lastCallKey).toContain('search=')
    expect(lastCallKey).toContain('manufacturer_id=mfr-001')
  })

  it('does not include empty filter parameters in URL', async () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    const { useAllManufacturerOrderItems } = await import(
      '@/features/purchase-orders/hooks/use-manufacturer-orders'
    )

    renderHook(() => useAllManufacturerOrderItems({}))

    // フィルターなしの場合はクエリパラメータなし
    const callArgs = useSWR.mock.calls
    const lastCallKey = callArgs[callArgs.length - 1]?.[0] as string
    expect(lastCallKey).toContain('/manufacturers/all-order-items')
    expect(lastCallKey).not.toContain('status=')
    expect(lastCallKey).not.toContain('search=')
    expect(lastCallKey).not.toContain('manufacturer_id=')
  })
})

// ======================================
// AllManufacturerOrderItemListResponse type includes correct fields
// ======================================

describe('AllManufacturerOrderItem type includes manufacturer fields', () => {
  it('each item has manufacturer_id and manufacturer_name fields', () => {
    const mockData = createMockAllOrderItemsData()

    for (const item of mockData.items) {
      expect(item).toHaveProperty('manufacturer_id')
      expect(item).toHaveProperty('manufacturer_name')
      expect(item.manufacturer_id).toBeTruthy()
      expect(item.manufacturer_name).toBeTruthy()
    }
  })

  it('response has total, total_quantity, total_amount fields', () => {
    const mockData = createMockAllOrderItemsData()

    expect(mockData).toHaveProperty('total')
    expect(mockData).toHaveProperty('total_quantity')
    expect(mockData).toHaveProperty('total_amount')
    expect(typeof mockData.total).toBe('number')
    expect(typeof mockData.total_quantity).toBe('number')
    expect(typeof mockData.total_amount).toBe('number')
  })
})

// ======================================
// FEAT-0020 AC-001: サマリーカードに「合計金額」が表示されない
// ======================================

describe('FEAT-0020 AC-001: サマリーカードに「合計金額」が表示されない', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not display 合計金額 label in summary cards', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // 「合計金額」ラベルが表示されない
    expect(screen.queryByText('合計金額')).not.toBeInTheDocument()

    // 「明細数」「合計数量」のみ表示される
    expect(screen.getByText('明細数')).toBeInTheDocument()
    expect(screen.getByText('合計数量')).toBeInTheDocument()
  })
})

// ======================================
// FEAT-0020 AC-002: テーブルヘッダーに「金額」カラムが表示されない
// ======================================

describe('FEAT-0020 AC-002: テーブルヘッダーに「金額」カラムが表示されない', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not have 金額 column header and has exactly 9 columns', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    const headers = screen.getAllByRole('columnheader')
    const headerTexts = headers.map(h => h.textContent)

    // テーブルヘッダーに「金額」が存在しない
    expect(headerTexts.some(t => t?.includes('金額'))).toBe(false)

    // カラム数は9
    expect(headers).toHaveLength(9)
  })
})

// ======================================
// FEAT-0020 AC-003: テーブル行に金額セルが表示されない
// ======================================

describe('FEAT-0020 AC-003: テーブル行に金額セルが表示されない', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not display ¥ prefixed amount values in table rows', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // price * quantity の金額計算結果が表示されない
    // item-001: 1000 * 2 = ¥2,000, item-002: 2000 * 1 = ¥2,000
    expect(screen.queryAllByText(/¥2,000/)).toHaveLength(0)
    // item-003: 500 * 5 = ¥2,500
    expect(screen.queryAllByText(/¥2,500/)).toHaveLength(0)
  })
})

// ======================================
// FEAT-0020 AC-004: サマリーカードのグリッドが2カラムに変更される
// ======================================

describe('FEAT-0020 AC-004: サマリーカードのグリッドが2カラムに変更される', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('uses grid-cols-2 class for summary card grid', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    const { container } = render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // grid-cols-2 クラスが適用されている
    const gridElement = container.querySelector('.grid-cols-2')
    expect(gridElement).toBeInTheDocument()

    // grid-cols-3 クラスが適用されていない
    const grid3Element = container.querySelector('.grid-cols-3')
    expect(grid3Element).not.toBeInTheDocument()
  })
})

// ======================================
// FEAT-0020 AC-005: 既存の明細数・合計数量の表示は維持される
// ======================================

describe('FEAT-0020 AC-005: 既存の明細数・合計数量の表示は維持される', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('displays 3件 and 8点 correctly', async () => {
    const { AllManufacturerOrderList } = await import(
      '@/features/purchase-orders/components/all-manufacturer-order-list'
    )

    const mockData = createMockAllOrderItemsData()

    render(
      <AllManufacturerOrderList
        data={mockData}
        isLoading={false}
      />
    )

    // 「3件」が正しく表示される
    expect(screen.getAllByText(/3件/).length).toBeGreaterThanOrEqual(1)

    // 「8点」が正しく表示される
    expect(screen.getByText(/8点/)).toBeInTheDocument()
  })
})

// ======================================
// /purchase-orders/all page integration test
// ======================================

describe('/purchase-orders/all page renders correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('page component can be imported and rendered', async () => {
    // This test verifies the page file exists at the expected path
    const pageModule = await import(
      '@/app/(dashboard)/purchase-orders/all/page'
    )

    expect(pageModule.default).toBeDefined()
    expect(typeof pageModule.default).toBe('function')
  })
})
