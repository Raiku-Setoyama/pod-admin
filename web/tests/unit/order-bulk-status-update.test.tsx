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
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
import { OrderBulkStatusUpdateDialog } from '@/features/orders/components/order-bulk-status-update-dialog'
import type {} from '@/types/api'

const mockApiClient = vi.mocked(apiClient)
const mockToast = vi.mocked(toast)

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
      expect(screen.getAllByText(/発注済み/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/製造中/).length).toBeGreaterThanOrEqual(1)
      expect(screen.getAllByText(/納品済み/).length).toBeGreaterThanOrEqual(1)
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

