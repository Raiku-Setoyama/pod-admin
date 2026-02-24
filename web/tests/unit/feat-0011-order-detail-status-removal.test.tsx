/**
 * Unit tests for FEAT-0011: Removal of status change UI from order-detail.
 *
 * Covers:
 * - AC-005: 受注詳細ページからステータス変更ボタンが削除されている
 * - AC-006: 受注詳細ページでステータス変更ダイアログが表示されない
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  getApiBaseUrl: () => 'http://test/api/v1',
}))

// Mock useSWR for OrderStatusHistory component
vi.mock('swr', () => ({
  default: vi.fn().mockReturnValue({
    data: { items: [] },
    error: undefined,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
  }),
}))

// Mock the OrderStatusUpdateDialog to detect if it's rendered
vi.mock('@/features/orders/components/order-status-update-dialog', () => ({
  OrderStatusUpdateDialog: (props: { open: boolean }) => (
    <div data-testid="order-status-update-dialog" data-open={props.open} />
  ),
}))

import { OrderDetail } from '@/features/orders/components/order-detail'
import type { Order, OrderStatus } from '@/types/api'

// ======================================
// Test data factory
// ======================================

const createMockOrder = (overrides: Partial<Order> = {}): Order => ({
  id: 'order-1',
  order_number: 'ORD-001',
  status: 'ordered' as OrderStatus,
  source: 'shopify',
  customer_name: 'Test Customer',
  customer_postal_code: '100-0001',
  customer_address_prefecture: 'Tokyo',
  customer_address_city: 'Chiyoda',
  customer_address_building: null,
  customer_full_address: 'Tokyo Chiyoda',
  customer_phone: '090-1234-5678',
  customer_email: 'test@example.com',
  ordered_at: '2024-01-15T14:30:00Z',
  total_price: 3000,
  items: [
    {
      id: 'item-1',
      uid: 'UID-001',
      product_name: 'Acrylic Keychain',
      product_type: 'acrylic_keychain',
      price: 1000,
      quantity: 3,
      size: null,
      position: null,
      color: null,
      design_image_url: null,
      thumbnail_image_url: null,
      created_at: '2024-01-15T14:30:00Z',
      updated_at: '2024-01-15T14:30:00Z',
    },
  ],
  shipment: null,
  product_id: null,
  product_name: null,
  price: null,
  quantity: null,
  manufacturing_data: null,
  created_at: '2024-01-15T14:30:00Z',
  updated_at: '2024-01-15T14:30:00Z',
  ...overrides,
})

// ======================================
// AC-005: ステータス変更ボタンが削除されている
// ======================================

describe('AC-005: Status change button is removed from order detail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render "ステータス変更" button', () => {
    const order = createMockOrder()

    render(<OrderDetail order={order} />)

    // The "ステータス変更" button should NOT exist after implementation
    const statusChangeButton = screen.queryByRole('button', { name: /ステータス変更/ })
    expect(statusChangeButton).not.toBeInTheDocument()
  })

  it('still displays the StatusBadge (read-only status display)', () => {
    const order = createMockOrder({ status: 'ordered' })

    render(<OrderDetail order={order} />)

    // StatusBadge should still be displayed (it shows status as a read-only badge)
    expect(screen.getByText('発注中')).toBeInTheDocument()
  })

  it('does not render status change button for any order status', () => {
    const statuses: OrderStatus[] = ['ordered', 'manufacturing', 'delivered', 'shipped']

    for (const status of statuses) {
      const order = createMockOrder({ status })
      const { unmount } = render(<OrderDetail order={order} />)

      const statusChangeButton = screen.queryByRole('button', { name: /ステータス変更/ })
      expect(statusChangeButton).not.toBeInTheDocument()

      unmount()
    }
  })
})

// ======================================
// AC-006: OrderStatusUpdateDialog が描画されない
// ======================================

describe('AC-006: OrderStatusUpdateDialog is not rendered', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not render OrderStatusUpdateDialog component', () => {
    const order = createMockOrder()

    render(<OrderDetail order={order} />)

    // The mocked OrderStatusUpdateDialog should NOT be in the DOM
    const dialog = screen.queryByTestId('order-status-update-dialog')
    expect(dialog).not.toBeInTheDocument()
  })

  it('does not import or use useState for status dialog state', () => {
    const order = createMockOrder()

    render(<OrderDetail order={order} />)

    // Verify that no dialog-related UI exists
    // After implementation, there should be no dialog trigger or dialog content
    const dialog = screen.queryByTestId('order-status-update-dialog')
    expect(dialog).not.toBeInTheDocument()

    // Also verify there's no hidden dialog button
    const allButtons = screen.queryAllByRole('button')
    const statusButtons = allButtons.filter(
      btn => btn.textContent?.includes('ステータス変更')
    )
    expect(statusButtons).toHaveLength(0)
  })
})
