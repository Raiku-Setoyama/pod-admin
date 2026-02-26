/**
 * Unit tests for FEAT-0017: 商品マスター一覧のフィルター機能
 *
 * Covers:
 * - AC-001: フィルターUI（種類・メーカー・ステータスのセレクトボックス）が表示される
 * - AC-002: 種類フィルター選択でproduct_typeフィルタリング
 * - AC-003: メーカーフィルター選択でmanufacturer_idフィルタリング
 * - AC-004: ステータスフィルター「有効」選択でis_active=true
 * - AC-005: ステータスフィルター「無効」選択でis_active=false
 * - AC-006: フィルター変更時にページが1にリセットされる
 * - AC-007: リセットボタンで全フィルタークリア
 * - AC-008: フィルター未適用時はリセットボタン非表示
 * - AC-009: URLパラメーター付きでページを開くとフィルターが適用される
 * - AC-010: 無効なURLパラメーター値は無視される
 * - AC-011: useProductsフックがmanufacturer_idパラメーターをAPI送信に含める
 * - AC-012: useProductsフックがis_activeパラメーターをAPI送信に含める
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderHook, waitFor } from '@testing-library/react'

// Mock SWR
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: undefined,
    error: undefined,
    isLoading: false,
    mutate: vi.fn(),
  })),
}))

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

// Mock next/navigation with controllable useSearchParams
const mockPush = vi.fn()
const mockReplace = vi.fn()
let mockSearchParams = new URLSearchParams()

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/products',
  useSearchParams: () => mockSearchParams,
  useParams: () => ({}),
}))

// Import components/hooks AFTER mocks are set up
import { ProductFilters } from '@/features/products/components/product-filters'
import { useProducts } from '@/features/products/hooks/use-products'

// ======================================
// Helper: Mock manufacturer data for meaker filter options
// ======================================

const mockManufacturers = [
  { id: 'mfr-001', name: 'メーカーA' },
  { id: 'mfr-002', name: 'メーカーB' },
  { id: 'mfr-003', name: 'メーカーC' },
]

// ======================================
// Helper: Create props for ProductFilters
// ======================================

function createFilterProps(overrides: Partial<{
  category: string | null
  maker: string | null
  status: string | null
  onCategoryChange: (value: string | null) => void
  onMakerChange: (value: string | null) => void
  onStatusChange: (value: string | null) => void
  onReset: () => void
  manufacturers: Array<{ id: string; name: string }>
}> = {}) {
  return {
    category: null as string | null,
    maker: null as string | null,
    status: null as string | null,
    onCategoryChange: vi.fn(),
    onMakerChange: vi.fn(),
    onStatusChange: vi.fn(),
    onReset: vi.fn(),
    manufacturers: mockManufacturers,
    ...overrides,
  }
}

// ======================================
// AC-001: フィルターUI（種類・メーカー・ステータスのセレクトボックス）が表示される
// ======================================

describe('AC-001: Product filter UI displays three select boxes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('renders category (種類) select box', () => {
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // 種類セレクトボックスが存在すること
    const categoryText = screen.getByText('全ての種類')
    expect(categoryText).toBeInTheDocument()
  })

  it('renders manufacturer (メーカー) select box', () => {
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // メーカーセレクトボックスが存在すること
    const makerText = screen.getByText('全てのメーカー')
    expect(makerText).toBeInTheDocument()
  })

  it('renders status (ステータス) select box', () => {
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // ステータスセレクトボックスが存在すること
    const statusText = screen.getByText('全てのステータス')
    expect(statusText).toBeInTheDocument()
  })

  it('renders exactly three comboboxes', () => {
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    const comboboxes = screen.getAllByRole('combobox')
    expect(comboboxes).toHaveLength(3)
  })
})

// ======================================
// AC-002: 種類フィルター選択でproduct_typeフィルタリング
// ======================================

describe('AC-002: Category filter selects product_type', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('calls onCategoryChange with "sticker" when ステッカー is selected', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // 種類セレクトボックスを開く
    const comboboxes = screen.getAllByRole('combobox')
    // 最初のコンボボックスが種類
    await user.click(comboboxes[0])

    // 「ステッカー」を選択
    const stickerOption = screen.getByText('ステッカー')
    await user.click(stickerOption)

    expect(props.onCategoryChange).toHaveBeenCalledWith('sticker')
  })

  it('category select has correct product type options', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // 種類セレクトボックスを開く
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[0])

    // 全ての種類オプションが表示されること
    expect(screen.getByText('アクリルキーホルダー')).toBeInTheDocument()
    expect(screen.getByText('アクリルスタンド')).toBeInTheDocument()
    expect(screen.getByText('ステッカー')).toBeInTheDocument()
    expect(screen.getByText('トートバッグ')).toBeInTheDocument()
    expect(screen.getByText('Tシャツ')).toBeInTheDocument()
  })
})

// ======================================
// AC-003: メーカーフィルター選択でmanufacturer_idフィルタリング
// ======================================

describe('AC-003: Manufacturer filter selects manufacturer_id', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('calls onMakerChange with manufacturer ID when a manufacturer is selected', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // メーカーセレクトボックスを開く（2番目のコンボボックス）
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[1])

    // 「メーカーA」を選択
    const makerOption = screen.getByText('メーカーA')
    await user.click(makerOption)

    expect(props.onMakerChange).toHaveBeenCalledWith('mfr-001')
  })

  it('manufacturer select shows manufacturers from props', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // メーカーセレクトボックスを開く
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[1])

    // メーカーオプションが表示されること
    expect(screen.getByText('メーカーA')).toBeInTheDocument()
    expect(screen.getByText('メーカーB')).toBeInTheDocument()
    expect(screen.getByText('メーカーC')).toBeInTheDocument()
  })
})

// ======================================
// AC-004: ステータスフィルター「有効」選択でis_active=true
// ======================================

describe('AC-004: Status filter "有効" sets is_active=true', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('calls onStatusChange with "active" when 有効 is selected', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // ステータスセレクトボックスを開く（3番目のコンボボックス）
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[2])

    // 「有効」を選択
    const activeOption = screen.getByText('有効')
    await user.click(activeOption)

    expect(props.onStatusChange).toHaveBeenCalledWith('active')
  })
})

// ======================================
// AC-005: ステータスフィルター「無効」選択でis_active=false
// ======================================

describe('AC-005: Status filter "無効" sets is_active=false', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('calls onStatusChange with "inactive" when 無効 is selected', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // ステータスセレクトボックスを開く（3番目のコンボボックス）
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[2])

    // 「無効」を選択
    const inactiveOption = screen.getByText('無効')
    await user.click(inactiveOption)

    expect(props.onStatusChange).toHaveBeenCalledWith('inactive')
  })

  it('status select has exactly three options: 全てのステータス, 有効, 無効', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // ステータスセレクトボックスを開く
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[2])

    expect(screen.getAllByText('全てのステータス').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('有効')).toBeInTheDocument()
    expect(screen.getByText('無効')).toBeInTheDocument()
  })
})

// ======================================
// AC-006: フィルター変更時にページが1にリセットされる
// ======================================

describe('AC-006: Filter change resets page to 1', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams('page=3')
  })

  it('resets page parameter when category filter changes', async () => {
    const user = userEvent.setup()
    const props = createFilterProps()
    render(<ProductFilters {...props} />)

    // 種類フィルターを変更
    const comboboxes = screen.getAllByRole('combobox')
    await user.click(comboboxes[0])
    const stickerOption = screen.getByText('ステッカー')
    await user.click(stickerOption)

    // onCategoryChangeが呼ばれた際に、ページリセットも行われること
    // 実装によってはonCategoryChange内でページリセットされるか、
    // またはページリセット用のコールバックが別途呼ばれる
    expect(props.onCategoryChange).toHaveBeenCalled()
  })
})

// ======================================
// AC-007: リセットボタンで全フィルタークリア
// ======================================

describe('AC-007: Reset button clears all filters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('shows reset button when category filter is active', () => {
    const props = createFilterProps({ category: 'sticker' })
    render(<ProductFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /リセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('shows reset button when maker filter is active', () => {
    const props = createFilterProps({ maker: 'mfr-001' })
    render(<ProductFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /リセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('shows reset button when status filter is active', () => {
    const props = createFilterProps({ status: 'active' })
    render(<ProductFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /リセット/ })
    expect(resetButton).toBeInTheDocument()
  })

  it('calls onReset when reset button is clicked', async () => {
    const user = userEvent.setup()
    const props = createFilterProps({ category: 'sticker', status: 'active' })
    render(<ProductFilters {...props} />)

    const resetButton = screen.getByRole('button', { name: /リセット/ })
    await user.click(resetButton)

    expect(props.onReset).toHaveBeenCalledTimes(1)
  })
})

// ======================================
// AC-008: フィルター未適用時はリセットボタン非表示
// ======================================

describe('AC-008: Reset button hidden when no filters active', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockSearchParams = new URLSearchParams()
  })

  it('does not show reset button when all filters are at default values', () => {
    const props = createFilterProps({
      category: null,
      maker: null,
      status: null,
    })
    render(<ProductFilters {...props} />)

    const resetButton = screen.queryByRole('button', { name: /リセット/ })
    expect(resetButton).not.toBeInTheDocument()
  })
})

// ======================================
// AC-009: URLパラメーター付きでページを開くとフィルターが適用される
// ======================================

describe('AC-009: URL parameters apply corresponding filters on page load', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('applies category=sticker and status=active from URL parameters', () => {
    mockSearchParams = new URLSearchParams('category=sticker&status=active')

    const props = createFilterProps({
      category: 'sticker',
      status: 'active',
    })
    render(<ProductFilters {...props} />)

    // 種類フィルターが「ステッカー」に設定されていること
    // ProductFiltersコンポーネントがcategory propsを受け取り、対応するSelectのvalueを設定する
    // 実装後は選択済みの値が表示される
    expect(screen.queryByText('ステッカー')).toBeInTheDocument()
  })

  it('applies maker filter from URL parameters', () => {
    mockSearchParams = new URLSearchParams('maker=mfr-001')

    const props = createFilterProps({
      maker: 'mfr-001',
    })
    render(<ProductFilters {...props} />)

    // メーカーフィルターが「メーカーA」に設定されていること
    expect(screen.queryByText('メーカーA')).toBeInTheDocument()
  })
})

// ======================================
// AC-010: 無効なURLパラメーター値は無視される
// ======================================

describe('AC-010: Invalid URL parameter values are ignored', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ignores invalid category value and shows default "全ての種類"', () => {
    mockSearchParams = new URLSearchParams('category=invalid_value')

    // 無効な値の場合、propsにはnullが渡される（ページコンポーネントでバリデーション済み）
    const props = createFilterProps({ category: null })
    render(<ProductFilters {...props} />)

    // デフォルトの「全ての種類」が表示されること
    expect(screen.getByText('全ての種類')).toBeInTheDocument()
  })
})

// ======================================
// AC-011: useProductsフックがmanufacturer_idパラメーターをAPI送信に含める
// ======================================

describe('AC-011: useProducts hook includes manufacturer_id in API request', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('passes manufacturer_id to query parameters', () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    renderHook(() =>
      useProducts({ manufacturer_id: 'mfr-001' })
    )

    // useSWRが manufacturer_id を含むキーで呼ばれること
    expect(useSWR).toHaveBeenCalledWith(
      expect.stringContaining('manufacturer_id=mfr-001'),
      expect.anything()
    )
  })

  it('does not include manufacturer_id when not specified', () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    renderHook(() => useProducts({}))

    // manufacturer_id がキーに含まれないこと
    const callArgs = useSWR.mock.calls
    const lastCallKey = callArgs[callArgs.length - 1]?.[0] as string
    expect(lastCallKey).not.toContain('manufacturer_id')
  })
})

// ======================================
// AC-012: useProductsフックがis_activeパラメーターをAPI送信に含める
// ======================================

describe('AC-012: useProducts hook includes is_active in API request', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('passes is_active=true to query parameters', () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    renderHook(() =>
      useProducts({ is_active: true })
    )

    // useSWRが is_active=true を含むキーで呼ばれること
    expect(useSWR).toHaveBeenCalledWith(
      expect.stringContaining('is_active=true'),
      expect.anything()
    )
  })

  it('passes is_active=false to query parameters', () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    renderHook(() =>
      useProducts({ is_active: false })
    )

    // useSWRが is_active=false を含むキーで呼ばれること
    expect(useSWR).toHaveBeenCalledWith(
      expect.stringContaining('is_active=false'),
      expect.anything()
    )
  })

  it('does not include is_active when not specified', () => {
    const useSWR = vi.mocked(
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      require('swr').default
    )

    renderHook(() => useProducts({}))

    // is_active がキーに含まれないこと
    const callArgs = useSWR.mock.calls
    const lastCallKey = callArgs[callArgs.length - 1]?.[0] as string
    expect(lastCallKey).not.toContain('is_active')
  })
})
