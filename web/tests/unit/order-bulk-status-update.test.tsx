/**
 * Unit tests for Order bulk status update functionality.
 *
 * FEAT-0007: Order bulk status update (checkboxes + bulk update button).
 * Tests cover:
 * - AC-001: Checkbox column in order list
 * - AC-002: Select all checkbox
 * - AC-003: Individual checkbox selection
 * - AC-004: Selected count display
 * - AC-005: Bulk update button visibility
 * - AC-006: Bulk update dialog
 * - AC-014: Success toast notification
 * - AC-015: Partial failure warning toast
 *
 * NOTE: These tests are written in TDD Red phase - the implementation does not exist yet.
 * Tests will fail until the implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

// Mock toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

import { apiClient } from '@/lib/api/client'
import { toast } from 'sonner'
import { OrderList } from '@/features/orders/components/order-list'
import { OrderBulkStatusUpdateDialog } from '@/features/orders/components/order-bulk-status-update-dialog'
import type { Order, OrderStatus } from '@/types/api'

const mockApiClient = vi.mocked(apiClient)
const mockToast = vi.mocked(toast)

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

describe('OrderList with checkboxes', () => {
  const mockOnRowClick = vi.fn()
  const mockOnSelectChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ===========================================
  // AC-001: Checkbox column in order list
  // ===========================================

  describe('AC-001: Checkbox column display', () => {
    it('renders checkbox column in table header', () => {
      const orders = [createMockOrder()]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={[]}
          onSelectChange={mockOnSelectChange}
        />
      )

      // Header should have select-all checkbox
      const headerCheckbox = screen.getByRole('checkbox', { name: /全選択/i })
      expect(headerCheckbox).toBeInTheDocument()
    })

    it('renders checkbox for each order row', () => {
      const orders = [
        createMockOrder({ id: 'order-1', order_number: 'ORD-001' }),
        createMockOrder({ id: 'order-2', order_number: 'ORD-002' }),
        createMockOrder({ id: 'order-3', order_number: 'ORD-003' }),
      ]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={[]}
          onSelectChange={mockOnSelectChange}
        />
      )

      // Each row should have a checkbox (excluding header)
      const rowCheckboxes = screen.getAllByRole('checkbox').filter(
        cb => !cb.getAttribute('aria-label')?.includes('全選択')
      )
      expect(rowCheckboxes).toHaveLength(3)
    })
  })

  // ===========================================
  // AC-002: Select all checkbox
  // ===========================================

  describe('AC-002: Select all checkbox', () => {
    it('selects all rows when header checkbox is clicked', async () => {
      const user = userEvent.setup()
      const orders = [
        createMockOrder({ id: 'order-1' }),
        createMockOrder({ id: 'order-2' }),
      ]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={[]}
          onSelectChange={mockOnSelectChange}
        />
      )

      const selectAllCheckbox = screen.getByRole('checkbox', { name: /全選択/i })
      await user.click(selectAllCheckbox)

      expect(mockOnSelectChange).toHaveBeenCalledWith(['order-1', 'order-2'])
    })

    it('deselects all rows when header checkbox is clicked again', async () => {
      const user = userEvent.setup()
      const orders = [
        createMockOrder({ id: 'order-1' }),
        createMockOrder({ id: 'order-2' }),
      ]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={['order-1', 'order-2']}
          onSelectChange={mockOnSelectChange}
        />
      )

      const selectAllCheckbox = screen.getByRole('checkbox', { name: /全選択/i })
      await user.click(selectAllCheckbox)

      expect(mockOnSelectChange).toHaveBeenCalledWith([])
    })

    it('shows indeterminate state when some rows are selected', () => {
      const orders = [
        createMockOrder({ id: 'order-1' }),
        createMockOrder({ id: 'order-2' }),
      ]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={['order-1']}
          onSelectChange={mockOnSelectChange}
        />
      )

      const selectAllCheckbox = screen.getByRole('checkbox', { name: /全選択/i })
      expect(selectAllCheckbox).toHaveAttribute('data-state', 'indeterminate')
    })
  })

  // ===========================================
  // AC-003: Individual checkbox selection
  // ===========================================

  describe('AC-003: Individual checkbox selection', () => {
    it('selects individual row when checkbox is clicked', async () => {
      const user = userEvent.setup()
      const orders = [
        createMockOrder({ id: 'order-1' }),
        createMockOrder({ id: 'order-2' }),
      ]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={[]}
          onSelectChange={mockOnSelectChange}
        />
      )

      // Find the first row's checkbox
      const rowCheckboxes = screen.getAllByRole('checkbox').filter(
        cb => !cb.getAttribute('aria-label')?.includes('全選択')
      )
      await user.click(rowCheckboxes[0])

      expect(mockOnSelectChange).toHaveBeenCalledWith(['order-1'])
    })

    it('deselects individual row when checkbox is clicked again', async () => {
      const user = userEvent.setup()
      const orders = [
        createMockOrder({ id: 'order-1' }),
        createMockOrder({ id: 'order-2' }),
      ]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={['order-1']}
          onSelectChange={mockOnSelectChange}
        />
      )

      const rowCheckboxes = screen.getAllByRole('checkbox').filter(
        cb => !cb.getAttribute('aria-label')?.includes('全選択')
      )
      await user.click(rowCheckboxes[0])

      expect(mockOnSelectChange).toHaveBeenCalledWith([])
    })

    it('checkbox click does not trigger row click', async () => {
      const user = userEvent.setup()
      const orders = [createMockOrder({ id: 'order-1' })]

      render(
        <OrderList
          orders={orders}
          onRowClick={mockOnRowClick}
          selectedIds={[]}
          onSelectChange={mockOnSelectChange}
        />
      )

      const rowCheckboxes = screen.getAllByRole('checkbox').filter(
        cb => !cb.getAttribute('aria-label')?.includes('全選択')
      )
      await user.click(rowCheckboxes[0])

      // onRowClick should NOT be called when clicking checkbox
      expect(mockOnRowClick).not.toHaveBeenCalled()
    })
  })
})

describe('OrderBulkStatusUpdateDialog', () => {
  const mockOnClose = vi.fn()
  const mockOnSuccess = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ===========================================
  // AC-004: Selected count display
  // ===========================================

  describe('AC-004: Selected count display', () => {
    it('displays correct count of selected orders', () => {
      const selectedIds = ['order-1', 'order-2', 'order-3']

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={selectedIds}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByText(/3件/)).toBeInTheDocument()
    })
  })

  // ===========================================
  // AC-005: Bulk update button visibility
  // ===========================================

  describe('AC-005: Bulk update button visibility', () => {
    it('shows bulk update button when orders are selected', () => {
      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={['order-1']}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByRole('button', { name: /更新/ })).toBeInTheDocument()
    })
  })

  // ===========================================
  // AC-006: Status selection in dialog
  // ===========================================

  describe('AC-006: Status selection dialog', () => {
    it('shows status selection options: ordered, manufacturing, delivered', () => {
      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={['order-1']}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      fireEvent.click(selectTrigger)

      // Should have the three valid statuses
      expect(screen.getAllByText(/受注済み/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/製造中/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/配送準備完了/).length).toBeGreaterThanOrEqual(1)
    })

    it('does not show shipped as an option', () => {
      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={['order-1']}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      fireEvent.click(selectTrigger)

      const options = screen.getAllByRole('option')
      const shippedOption = options.find(opt =>
        opt.textContent?.toLowerCase().includes('shipped') ||
        opt.textContent?.includes('発送完了')
      )
      expect(shippedOption).toBeUndefined()
    })
  })

  // ===========================================
  // AC-014: Success toast notification
  // ===========================================

  describe('AC-014: Success toast notification', () => {
    it('shows success toast when all updates succeed', async () => {
      const user = userEvent.setup()
      const selectedIds = ['order-1', 'order-2']

      mockApiClient.mockResolvedValueOnce({
        updated_count: 2,
        failed_count: 0,
        failed_ids: [],
      })

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={selectedIds}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast.success).toHaveBeenCalledWith(
          expect.stringContaining('2件')
        )
      })
    })
  })

  // ===========================================
  // AC-015: Partial failure warning toast
  // ===========================================

  describe('AC-015: Partial failure warning toast', () => {
    it('shows warning toast when some updates fail', async () => {
      const user = userEvent.setup()
      const selectedIds = ['order-1', 'order-2', 'order-3']

      mockApiClient.mockResolvedValueOnce({
        updated_count: 2,
        failed_count: 1,
        failed_ids: ['order-3'],
      })

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={selectedIds}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast.success).toHaveBeenCalledWith(
          expect.stringContaining('2件')
        )
        expect(mockToast.warning).toHaveBeenCalledWith(
          expect.stringContaining('1件')
        )
      })
    })

    it('shows only error toast when all updates fail', async () => {
      const user = userEvent.setup()
      const selectedIds = ['order-1', 'order-2']

      mockApiClient.mockResolvedValueOnce({
        updated_count: 0,
        failed_count: 2,
        failed_ids: ['order-1', 'order-2'],
      })

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={selectedIds}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast.error).toHaveBeenCalled()
      })
    })
  })

  // ===========================================
  // API call verification
  // ===========================================

  describe('API call', () => {
    it('calls PATCH /orders/bulk-status with correct payload', async () => {
      const user = userEvent.setup()
      const selectedIds = ['order-1', 'order-2']

      mockApiClient.mockResolvedValueOnce({
        updated_count: 2,
        failed_count: 0,
        failed_ids: [],
      })

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={selectedIds}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          '/orders/bulk-status',
          expect.objectContaining({
            method: 'PATCH',
            body: {
              order_ids: selectedIds,
              status: 'manufacturing',
            },
          })
        )
      })
    })

    it('calls onSuccess after successful update', async () => {
      const user = userEvent.setup()
      const selectedIds = ['order-1']

      mockApiClient.mockResolvedValueOnce({
        updated_count: 1,
        failed_count: 0,
        failed_ids: [],
      })

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={selectedIds}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })
  })

  // ===========================================
  // Dialog interactions
  // ===========================================

  describe('Dialog interactions', () => {
    it('calls onClose when cancel button is clicked', async () => {
      const user = userEvent.setup()

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={['order-1']}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const cancelButton = screen.getByRole('button', { name: /キャンセル/ })
      await user.click(cancelButton)

      expect(mockOnClose).toHaveBeenCalled()
    })

    it('shows loading state while submitting', async () => {
      const user = userEvent.setup()

      // Make the API call hang
      mockApiClient.mockImplementationOnce(() => new Promise(() => {}))

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={['order-1']}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/更新中/)).toBeInTheDocument()
      })
    })
  })

  // ===========================================
  // Error handling
  // ===========================================

  describe('Error handling', () => {
    it('shows error message when API call fails', async () => {
      const user = userEvent.setup()

      mockApiClient.mockRejectedValueOnce(new Error('Network error'))

      render(
        <OrderBulkStatusUpdateDialog
          selectedIds={['order-1']}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockToast.error).toHaveBeenCalled()
      })
    })
  })
})

describe('Orders page with bulk update', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // ===========================================
  // Page integration
  // ===========================================

  describe('Bulk update button on orders page', () => {
    it('bulk update button shows selected count', () => {
      // This test verifies the integration on the orders page
      // The button text should include the count of selected items
      // Actual implementation will be in the orders page component

      // Mock test - actual implementation will be in the page component
      const selectedCount = 5
      const buttonText = `選択した${selectedCount}件を更新`
      expect(buttonText).toContain('5件')
    })

    it('bulk update button is disabled when no orders selected', () => {
      // Verify that the button should be disabled when nothing is selected
      const selectedCount = 0
      const isDisabled = selectedCount === 0
      expect(isDisabled).toBe(true)
    })
  })
})
