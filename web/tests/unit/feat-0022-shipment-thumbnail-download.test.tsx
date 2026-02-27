/**
 * Unit tests for FEAT-0022: 配送サムネイル画像ZIPダウンロード
 *
 * Covers:
 * - AC-012: 「商品サムネイル」ボタンが受注CSVボタンの右横に表示される
 * - AC-013: selectedIds が空の場合、「商品サムネイル」ボタンが disabled になる
 * - AC-014: selectedIds が1件以上の場合、「商品サムネイル」ボタンが有効になる
 * - AC-015: ボタンクリック時に POST /shipments/download-thumbnails を呼び出しZIPがダウンロードされる
 * - AC-016: ダウンロード中はボタンが disabled になり「ダウンロード中...」と表示される
 * - AC-017: ダウンロード成功時に toast.success が表示される
 * - AC-018: ダウンロード失敗時に toast.error が表示される
 *
 * NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
 * Tests will fail until the implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// ======================================
// Mocks
// ======================================

// Mock next/navigation (required because ShipmentsPage uses useRouter)
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => '/shipments',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}))

// Mock API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  downloadFile: vi.fn(),
  downloadFileByPost: vi.fn(),
}))

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

// Mock useShipments hook with shipments data so we can test checkbox interaction
const mockMutate = vi.fn()
const mockShipments = [
  {
    id: 'shipment-1',
    status: 'pending',
    tracking_number: null,
    carrier: null,
    packing_photo_path: null,
    shipped_at: null,
    delivered_at: null,
    note: null,
    customer_name: 'Test Customer 1',
    customer_postal_code: '100-0001',
    customer_address_prefecture: '東京都',
    customer_address_city: '千代田区',
    customer_address_building: null,
    customer_full_address: '東京都千代田区',
    customer_phone: '090-1234-5678',
    items: [
      {
        id: 'si-1_oi-1',
        order_id: 'order-1',
        order_number: 'ORD-001',
        product_name: 'テスト商品1',
        quantity: 1,
        thumbnail_image_url: 'https://example.com/thumb1.png',
      },
    ],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'shipment-2',
    status: 'pending',
    tracking_number: null,
    carrier: null,
    packing_photo_path: null,
    shipped_at: null,
    delivered_at: null,
    note: null,
    customer_name: 'Test Customer 2',
    customer_postal_code: '100-0002',
    customer_address_prefecture: '東京都',
    customer_address_city: '渋谷区',
    customer_address_building: null,
    customer_full_address: '東京都渋谷区',
    customer_phone: '090-9876-5432',
    items: [
      {
        id: 'si-2_oi-2',
        order_id: 'order-2',
        order_number: 'ORD-002',
        product_name: 'テスト商品2',
        quantity: 1,
        thumbnail_image_url: 'https://example.com/thumb2.png',
      },
    ],
    created_at: '2026-01-02T00:00:00Z',
    updated_at: '2026-01-02T00:00:00Z',
  },
]

vi.mock('@/features/shipments/hooks/use-shipments', () => ({
  useShipments: () => ({
    shipments: mockShipments,
    total: mockShipments.length,
    page: 1,
    limit: 20,
    isLoading: false,
    error: null,
    mutate: mockMutate,
  }),
}))

// Mock SWR
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: null,
    error: null,
    isLoading: false,
    mutate: vi.fn(),
  })),
}))

// Mock child components that are not under test
vi.mock('@/features/shipments/components/shipment-filters', () => ({
  ShipmentFilters: () => <div data-testid="mock-shipment-filters">ShipmentFilters</div>,
}))

vi.mock('@/components/common/pagination', () => ({
  Pagination: () => <div data-testid="mock-pagination">Pagination</div>,
}))

vi.mock('@/components/common/loading-spinner', () => ({
  PageLoading: () => <div data-testid="mock-page-loading">Loading...</div>,
}))

vi.mock('@/constants/status', async (importOriginal) => {
  const actual = await importOriginal() as Record<string, unknown>
  return {
    ...actual,
    getShipmentStatusUpdateOptions: () => [
      { value: 'ready', label: '出荷準備中' },
      { value: 'shipped', label: '発送済み' },
    ],
  }
})

import { toast } from 'sonner'
import type { Shipment } from '@/types/api'

const mockToast = vi.mocked(toast)

// Import the page component AFTER mocks are set up
import ShipmentsPage from '@/app/(dashboard)/shipments/page'

// ======================================
// Helpers
// ======================================

/**
 * Find the thumbnail download button by its text content.
 */
function findThumbnailButton(): HTMLElement | null {
  return screen.queryByRole('button', { name: /商品サムネイル/ })
}

/**
 * Find the CSV export button.
 */
function findCsvButton(): HTMLElement | null {
  return screen.queryByRole('button', { name: /受注CSV/ })
}

/**
 * Select shipments by clicking checkboxes.
 */
async function selectShipments(user: ReturnType<typeof userEvent.setup>, count: number) {
  const checkboxes = screen.getAllByRole('checkbox')
  // Skip header checkbox (first one), click individual row checkboxes
  for (let i = 1; i <= count && i < checkboxes.length; i++) {
    await user.click(checkboxes[i])
  }
}

// ======================================
// AC-012: 「商品サムネイル」ボタンが受注CSVボタンの右横に表示される
// ======================================

describe('AC-012: Thumbnail download button is displayed next to CSV export button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the "商品サムネイル" button on the shipments page', () => {
    render(<ShipmentsPage />)

    const thumbnailButton = findThumbnailButton()
    expect(thumbnailButton).toBeInTheDocument()
  })

  it('renders the "商品サムネイル" button alongside the "受注CSV" button', () => {
    render(<ShipmentsPage />)

    const thumbnailButton = findThumbnailButton()
    const csvButton = findCsvButton()

    expect(thumbnailButton).toBeInTheDocument()
    expect(csvButton).toBeInTheDocument()

    // Both should be siblings within the same container
    expect(thumbnailButton?.parentElement).toBe(csvButton?.parentElement)
  })
})

// ======================================
// AC-013: selectedIds が空の場合、「商品サムネイル」ボタンが disabled になる
// ======================================

describe('AC-013: Thumbnail button is disabled when no shipments are selected', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('disables the "商品サムネイル" button when no shipments are selected', () => {
    render(<ShipmentsPage />)

    const thumbnailButton = findThumbnailButton()
    expect(thumbnailButton).toBeInTheDocument()
    expect(thumbnailButton).toBeDisabled()
  })
})

// ======================================
// AC-014: selectedIds が1件以上の場合、「商品サムネイル」ボタンが有効になる
// ======================================

describe('AC-014: Thumbnail button is enabled when one or more shipments are selected', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('enables the "商品サムネイル" button when one shipment is selected', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Select one shipment
    await selectShipments(user, 1)

    const thumbnailButton = findThumbnailButton()
    expect(thumbnailButton).toBeInTheDocument()
    expect(thumbnailButton).not.toBeDisabled()
  })

  it('enables the "商品サムネイル" button when multiple shipments are selected', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Select two shipments
    await selectShipments(user, 2)

    const thumbnailButton = findThumbnailButton()
    expect(thumbnailButton).toBeInTheDocument()
    expect(thumbnailButton).not.toBeDisabled()
  })
})

// ======================================
// AC-015: ボタンクリック時に POST /shipments/download-thumbnails を呼び出し
// ======================================

describe('AC-015: Clicking the button triggers thumbnail ZIP download', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock global fetch for the download
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['fake-zip-data'], { type: 'application/zip' })),
      headers: new Headers({
        'Content-Disposition': "attachment; filename*=UTF-8''%E9%85%8D%E9%80%81%E3%82%B5%E3%83%A0%E3%83%8D%E3%82%A4%E3%83%AB_20260227_120000.zip",
      }),
    }) as unknown as typeof global.fetch

    // Mock URL and DOM methods for download
    global.URL.createObjectURL = vi.fn(() => 'blob:test-url')
    global.URL.revokeObjectURL = vi.fn()
  })

  it('calls fetch with POST /shipments/download-thumbnails when button is clicked', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Select one shipment
    await selectShipments(user, 1)

    // Click the thumbnail download button
    const thumbnailButton = findThumbnailButton()
    expect(thumbnailButton).toBeInTheDocument()
    expect(thumbnailButton).not.toBeDisabled()
    await user.click(thumbnailButton!)

    // fetch should be called with the correct URL and body
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/shipments/download-thumbnails'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('shipment_ids'),
        })
      )
    })
  })
})

// ======================================
// AC-016: ダウンロード中はボタンが disabled になり「ダウンロード中...」と表示される
// ======================================

describe('AC-016: Button shows loading state during download', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "ダウンロード中..." and disables button during download', async () => {
    const user = userEvent.setup()

    // Create a slow fetch that we can control
    let resolveFetch: (value: unknown) => void
    const fetchPromise = new Promise((resolve) => {
      resolveFetch = resolve
    })
    global.fetch = vi.fn().mockReturnValue(fetchPromise) as unknown as typeof global.fetch

    render(<ShipmentsPage />)

    // Select one shipment
    await selectShipments(user, 1)

    // Click the thumbnail download button
    const thumbnailButton = findThumbnailButton()
    await user.click(thumbnailButton!)

    // During download, button should be disabled and show loading text
    await waitFor(() => {
      const loadingButton = screen.getByRole('button', { name: /ダウンロード中/ })
      expect(loadingButton).toBeInTheDocument()
      expect(loadingButton).toBeDisabled()
    })

    // Resolve the fetch
    resolveFetch!({
      ok: true,
      blob: () => Promise.resolve(new Blob(['data'], { type: 'application/zip' })),
      headers: new Headers({
        'Content-Disposition': "attachment; filename*=UTF-8''test.zip",
      }),
    })
  })
})

// ======================================
// AC-017: ダウンロード成功時に toast.success が表示される
// ======================================

describe('AC-017: Shows success toast after successful download', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(['fake-zip-data'], { type: 'application/zip' })),
      headers: new Headers({
        'Content-Disposition': "attachment; filename*=UTF-8''test.zip",
      }),
    }) as unknown as typeof global.fetch

    global.URL.createObjectURL = vi.fn(() => 'blob:test-url')
    global.URL.revokeObjectURL = vi.fn()
  })

  it('shows toast.success after download completes successfully', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Select one shipment
    await selectShipments(user, 1)

    // Click the thumbnail download button
    const thumbnailButton = findThumbnailButton()
    await user.click(thumbnailButton!)

    // toast.success should be called
    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalled()
    })
  })
})

// ======================================
// AC-018: ダウンロード失敗時に toast.error が表示される
// ======================================

describe('AC-018: Shows error toast after download failure', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    }) as unknown as typeof global.fetch
  })

  it('shows toast.error when download request fails', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Select one shipment
    await selectShipments(user, 1)

    // Click the thumbnail download button
    const thumbnailButton = findThumbnailButton()
    await user.click(thumbnailButton!)

    // toast.error should be called
    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalled()
    })
  })

  it('shows toast.error when download throws an exception', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error')) as unknown as typeof global.fetch

    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Select one shipment
    await selectShipments(user, 1)

    // Click the thumbnail download button
    const thumbnailButton = findThumbnailButton()
    await user.click(thumbnailButton!)

    // toast.error should be called
    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalled()
    })
  })
})
