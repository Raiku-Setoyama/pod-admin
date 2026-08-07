/**
 * Unit tests for FEAT-0018: 受注イメージ画像ZIPダウンロード
 *
 * Covers:
 * - AC-001: 受注を1件以上選択した状態で「イメージ画像ダウンロード」ボタンが表示される
 * - AC-002: 受注が未選択の場合は「イメージ画像ダウンロード」ボタンが表示されない
 * - AC-011: ボタンクリック時にダウンロードが開始される
 *
 * NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
 * Tests will fail until the implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock SWR - use vi.hoisted to create a spy function that can be referenced in vi.mock
const { mockUseSWR } = vi.hoisted(() => ({
  mockUseSWR: vi.fn((..._args: unknown[]) => ({
    data: undefined as unknown,
    error: undefined,
    isLoading: false,
    mutate: vi.fn(),
    isValidating: false,
  })),
}))

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  downloadFile: vi.fn(),
  downloadFileByPost: vi.fn(),
}))

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

vi.mock('swr', () => ({
  default: mockUseSWR,
}))

// Mock next/navigation
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
  usePathname: () => '/orders',
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({}),
}))

import { downloadFileByPost } from '@/lib/api/client'
import { toast } from 'sonner'
import type { Order, OrderStatus } from '@/types/api'

const mockDownloadFileByPost = vi.mocked(downloadFileByPost)
const mockToast = vi.mocked(toast)

// Import the page component - will fail until implementation exists
import OrdersPage from '@/app/(dashboard)/orders/page'

// ======================================
// Helper: Create mock order data
// ======================================

const createMockOrder = (overrides: Partial<Order> = {}): Order => ({
  id: 'order-123',
  order_number: 'TEST-001',
  status: 'ordered' as OrderStatus,
  source: 'test-source',
  order_source_id: 'source-123',
  customer_name: 'Test Customer',
  customer_postal_code: '100-0001',
  customer_address_prefecture: 'Tokyo',
  customer_address_city: 'Chiyoda',
  customer_address_building: null,
  customer_full_address: 'Tokyo Chiyoda',
  customer_phone: '090-1234-5678',
  customer_email: 'test@example.com',
  ordered_at: '2024-01-01T00:00:00Z',
  estimated_shipping_date: null,
  total_price: 1000,
  items: [],
  shipment: null,
  product_id: null,
  product_name: null,
  price: null,
  quantity: null,
  manufacturing_data: null,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  ...overrides,
})

// ======================================
// Setup: Mock SWR to return orders
// ======================================

function setupOrdersMock(orders: Order[]) {
  mockUseSWR.mockReturnValue({
    data: {
      items: orders,
      total: orders.length,
      page: 1,
      limit: 20,
    },
    error: undefined,
    isLoading: false,
    mutate: vi.fn(),
    isValidating: false,
  })
}

// ======================================
// AC-001: 受注を1件以上選択した状態で「イメージ画像ダウンロード」ボタンが表示される
// ======================================

describe('AC-001: Image download button shown when orders selected', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "イメージ画像ダウンロード" button when one or more orders are selected', async () => {
    const user = userEvent.setup()
    const orders = [
      createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
      createMockOrder({ id: 'order-2', order_number: 'ORD-002' }),
    ]
    setupOrdersMock(orders)

    render(<OrdersPage />)

    // Select the first order by clicking its checkbox (aria-label = "ORD-001を選択")
    const firstOrderCheckbox = screen.getByRole('checkbox', { name: /ORD-001を選択/ })
    await user.click(firstOrderCheckbox)

    // "イメージ画像ダウンロード" button should appear
    await waitFor(() => {
      const downloadButton = screen.getByRole('button', { name: /イメージ画像ダウンロード/ })
      expect(downloadButton).toBeInTheDocument()
    })
  })

  it('shows image download button when multiple orders are selected', async () => {
    const user = userEvent.setup()
    const orders = [
      createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
      createMockOrder({ id: 'order-2', order_number: 'ORD-002' }),
      createMockOrder({ id: 'order-3', order_number: 'ORD-003' }),
    ]
    setupOrdersMock(orders)

    render(<OrdersPage />)

    // Select all by clicking header checkbox (aria-label = "すべて選択")
    const selectAllCheckbox = screen.getByRole('checkbox', { name: /すべて選択/ })
    await user.click(selectAllCheckbox)

    // "イメージ画像ダウンロード" button should appear
    await waitFor(() => {
      const downloadButton = screen.getByRole('button', { name: /イメージ画像ダウンロード/ })
      expect(downloadButton).toBeInTheDocument()
    })
  })
})

// ======================================
// AC-002: 受注が未選択の場合は「イメージ画像ダウンロード」ボタンが表示されない
// ======================================

describe('AC-002: Image download button hidden when no orders selected', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not show "イメージ画像ダウンロード" button when no orders are selected', () => {
    const orders = [
      createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
      createMockOrder({ id: 'order-2', order_number: 'ORD-002' }),
    ]
    setupOrdersMock(orders)

    render(<OrdersPage />)

    // "イメージ画像ダウンロード" button should NOT be visible
    const downloadButton = screen.queryByRole('button', { name: /イメージ画像ダウンロード/ })
    expect(downloadButton).not.toBeInTheDocument()
  })

  it('hides image download button when orders are deselected', async () => {
    const user = userEvent.setup()
    const orders = [
      createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
    ]
    setupOrdersMock(orders)

    render(<OrdersPage />)

    // Select the first order (aria-label = "ORD-001を選択")
    const firstOrderCheckbox = screen.getByRole('checkbox', { name: /ORD-001を選択/ })
    await user.click(firstOrderCheckbox)

    // Button should appear
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /イメージ画像ダウンロード/ })).toBeInTheDocument()
    })

    // Deselect the order
    await user.click(firstOrderCheckbox)

    // Button should disappear
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /イメージ画像ダウンロード/ })).not.toBeInTheDocument()
    })
  })
})

// ======================================
// AC-011: ボタンクリック時にダウンロードが開始される
// ======================================

describe('AC-011: Download starts when button is clicked', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls downloadFileByPost with correct order_ids when button is clicked', async () => {
    const user = userEvent.setup()
    const orders = [
      createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
      createMockOrder({ id: 'order-2', order_number: 'ORD-002' }),
    ]
    setupOrdersMock(orders)

    mockDownloadFileByPost.mockResolvedValueOnce(undefined)

    render(<OrdersPage />)

    // Select both orders using the "すべて選択" checkbox
    const selectAllCheckbox = screen.getByRole('checkbox', { name: /すべて選択/ })
    await user.click(selectAllCheckbox)

    // Click the download button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /イメージ画像ダウンロード/ })).toBeInTheDocument()
    })
    const downloadButton = screen.getByRole('button', { name: /イメージ画像ダウンロード/ })
    await user.click(downloadButton)

    // downloadFileByPost should be called with the selected order IDs
    await waitFor(() => {
      expect(mockDownloadFileByPost).toHaveBeenCalledWith(
        '/orders/download-images',
        { order_ids: ['order-1', 'order-2'] },
        expect.stringContaining('受注画像_')
      )
    })
  })

  it('shows error toast when download fails', async () => {
    const user = userEvent.setup()
    const orders = [
      createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
    ]
    setupOrdersMock(orders)

    mockDownloadFileByPost.mockRejectedValueOnce(new Error('Download failed'))

    render(<OrdersPage />)

    // Select the order (aria-label = "ORD-001を選択")
    const firstOrderCheckbox = screen.getByRole('checkbox', { name: /ORD-001を選択/ })
    await user.click(firstOrderCheckbox)

    // Click the download button
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /イメージ画像ダウンロード/ })).toBeInTheDocument()
    })
    const downloadButton = screen.getByRole('button', { name: /イメージ画像ダウンロード/ })
    await user.click(downloadButton)

    // Error toast should be shown
    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith('画像のダウンロードに失敗しました')
    })
  })
})
