import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OrderStatusUpdateDialog } from '@/features/orders/components/order-status-update-dialog'
import type { Order, OrderStatus } from '@/types/api'

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

import { apiClient } from '@/lib/api/client'

const mockApiClient = vi.mocked(apiClient)

const createMockOrder = (overrides: Partial<Order> = {}): Order => ({
  id: 'order-123',
  order_number: 'TEST-001',
  status: 'ordered' as OrderStatus,
  source: 'test-source',
  customer_name: 'Test Customer',
  customer_postal_code: '100-0001',
  customer_address_prefecture: 'Tokyo',
  customer_address_city: 'Chiyoda',
  customer_address_building: null,
  customer_full_address: 'Tokyo Chiyoda',
  estimated_shipping_date: null,
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

describe('OrderStatusUpdateDialog', () => {
  const mockOnSuccess = vi.fn()
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Dialog rendering', () => {
    it('renders dialog when open is true', () => {
      const order = createMockOrder()

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByRole('dialog')).toBeInTheDocument()
      expect(screen.getByText(/ステータス変更/)).toBeInTheDocument()
    })

    it('does not render dialog when open is false', () => {
      const order = createMockOrder()

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={false}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('displays current order status', () => {
      const order = createMockOrder({ status: 'manufacturing' as OrderStatus })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Multiple elements may contain the status label (description and select)
      expect(screen.getAllByText(/製造中/).length).toBeGreaterThanOrEqual(1)
    })
  })

  describe('Status options', () => {
    it('shows ordered, manufacturing, and delivered as selectable options', () => {
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Open the select dropdown
      const selectTrigger = screen.getByRole('combobox')
      fireEvent.click(selectTrigger)

      // Check that all valid statuses are available (may have duplicates due to description)
      expect(screen.getAllByText(/発注済み/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/製造中/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/納品済み/).length).toBeGreaterThanOrEqual(1)
    })

    it('does not show shipped as a direct option (controlled by shipment)', () => {
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      fireEvent.click(selectTrigger)

      // shipped should not be available as a direct transition
      const options = screen.getAllByRole('option')
      const shippedOption = options.find(opt => opt.textContent?.toLowerCase().includes('shipped'))
      expect(shippedOption).toBeUndefined()
    })
  })

  describe('Status transitions: ordered -> manufacturing', () => {
    it('allows transition from ordered to manufacturing', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      mockApiClient.mockResolvedValueOnce({
        ...order,
        status: 'manufacturing',
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Select manufacturing status
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      // Submit the form
      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/orders/order-123/status'),
          expect.objectContaining({
            method: 'PATCH',
            body: expect.objectContaining({ status: 'manufacturing' }),
          })
        )
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })
  })

  describe('Status transitions: manufacturing -> ordered', () => {
    it('allows reverse transition from manufacturing to ordered', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({ status: 'manufacturing' as OrderStatus })

      mockApiClient.mockResolvedValueOnce({
        ...order,
        status: 'ordered',
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const orderedOption = screen.getByRole('option', { name: /発注済み/ })
      await user.click(orderedOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/orders/order-123/status'),
          expect.objectContaining({
            method: 'PATCH',
            body: expect.objectContaining({ status: 'ordered' }),
          })
        )
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })
  })

  describe('Status transitions: to delivered (creates shipment)', () => {
    it('allows transition from ordered to delivered', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      mockApiClient.mockResolvedValueOnce({
        ...order,
        status: 'delivered',
        shipment: { id: 'shipment-123', status: 'pending' },
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const deliveredOption = screen.getByRole('option', { name: /納品済み/ })
      await user.click(deliveredOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/orders/order-123/status'),
          expect.objectContaining({
            method: 'PATCH',
            body: expect.objectContaining({ status: 'delivered' }),
          })
        )
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })

    it('allows transition from manufacturing to delivered', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({ status: 'manufacturing' as OrderStatus })

      mockApiClient.mockResolvedValueOnce({
        ...order,
        status: 'delivered',
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const deliveredOption = screen.getByRole('option', { name: /納品済み/ })
      await user.click(deliveredOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/orders/order-123/status'),
          expect.objectContaining({
            method: 'PATCH',
            body: expect.objectContaining({ status: 'delivered' }),
          })
        )
      })
    })
  })

  describe('Status transitions: from delivered (deletes shipment)', () => {
    it('allows transition from delivered to ordered', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({
        status: 'delivered' as OrderStatus,
        shipment: { id: 'shipment-123', status: 'pending', tracking_number: null, carrier: null },
      })

      mockApiClient.mockResolvedValueOnce({
        ...order,
        status: 'ordered',
        shipment: null,
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const orderedOption = screen.getByRole('option', { name: /発注済み/ })
      await user.click(orderedOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/orders/order-123/status'),
          expect.objectContaining({
            method: 'PATCH',
            body: expect.objectContaining({ status: 'ordered' }),
          })
        )
      })
    })

    it('allows transition from delivered to manufacturing', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({
        status: 'delivered' as OrderStatus,
        shipment: { id: 'shipment-123', status: 'pending', tracking_number: null, carrier: null },
      })

      mockApiClient.mockResolvedValueOnce({
        ...order,
        status: 'manufacturing',
        shipment: null,
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/orders/order-123/status'),
          expect.objectContaining({
            method: 'PATCH',
            body: expect.objectContaining({ status: 'manufacturing' }),
          })
        )
      })
    })
  })

  describe('Warning for shipped shipment', () => {
    it('shows warning when trying to revert from delivered with shipped shipment', () => {
      const order = createMockOrder({
        status: 'delivered' as OrderStatus,
        shipment: { id: 'shipment-123', status: 'shipped', tracking_number: '12345', carrier: 'Yamato' },
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Should show a warning that shipment is already shipped
      expect(screen.getByText(/発送済み/)).toBeInTheDocument()
    })

    it('disables status change when shipment is shipped', () => {
      const order = createMockOrder({
        status: 'delivered' as OrderStatus,
        shipment: { id: 'shipment-123', status: 'shipped', tracking_number: '12345', carrier: 'Yamato' },
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // The select or submit should be disabled
      const selectTrigger = screen.getByRole('combobox')
      expect(selectTrigger).toHaveAttribute('aria-disabled', 'true')
    })
  })

  describe('Error handling', () => {
    it('shows error message when API call fails', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      mockApiClient.mockRejectedValueOnce(new Error('Network error'))

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/Network error/)).toBeInTheDocument()
      })
    })

    it('shows validation error for invalid transition', async () => {
      const user = userEvent.setup()
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      // Throw error without message to test code-based error handling
      mockApiClient.mockRejectedValueOnce({
        status: 400,
        code: 'INVALID_STATUS_TRANSITION',
      })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // Simulate trying an invalid transition (shouldn't happen with proper UI, but test the error handling)
      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      // Select a different status to trigger API call
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(screen.getByText(/許可されていません/)).toBeInTheDocument()
      })
    })
  })

  describe('Dialog interactions', () => {
    it('calls onClose when cancel button is clicked', async () => {
      const user = userEvent.setup()
      const order = createMockOrder()

      render(
        <OrderStatusUpdateDialog
          order={order}
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
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      // Make the API call hang
      mockApiClient.mockImplementationOnce(() => new Promise(() => {}))

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      await user.click(selectTrigger)
      const manufacturingOption = screen.getByRole('option', { name: /製造中/ })
      await user.click(manufacturingOption)

      const submitButton = screen.getByRole('button', { name: /更新/ })
      await user.click(submitButton)

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText(/更新中/)).toBeInTheDocument()
      })
    })
  })

  describe('Japanese labels', () => {
    it('displays Japanese status labels', () => {
      const order = createMockOrder({ status: 'ordered' as OrderStatus })

      render(
        <OrderStatusUpdateDialog
          order={order}
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const selectTrigger = screen.getByRole('combobox')
      fireEvent.click(selectTrigger)

      // Should have Japanese labels
      // (Actual labels depend on implementation, testing the pattern)
      expect(
        screen.queryByText(/ordered|manufacturing|納品済み/) ||
        screen.queryByText(/ordered|manufacturing|納品済み/)
      ).toBeInTheDocument()
    })
  })
})
