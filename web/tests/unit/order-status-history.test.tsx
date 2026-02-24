/**
 * Unit tests for OrderStatusHistory component.
 *
 * FEAT-0014: AC-007, AC-008, AC-009
 * Tests verify the status history timeline section in the order detail page.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { OrderStatusHistory } from '@/features/orders/components/order-status-history'
import type { OrderStatusHistory as OrderStatusHistoryType } from '@/types/api'

// Mock useSWR for data fetching
vi.mock('swr', () => ({
  default: vi.fn(),
}))

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  getApiBaseUrl: () => 'http://test/api/v1',
}))

import useSWR from 'swr'

const mockUseSWR = vi.mocked(useSWR)

const createMockHistoryItem = (overrides: Partial<OrderStatusHistoryType> = {}): OrderStatusHistoryType => ({
  id: 'history-123',
  order_id: 'order-123',
  from_status: 'ordered',
  to_status: 'manufacturing',
  changed_by: 'Test Admin',
  note: null,
  created_at: '2026-01-15T10:30:00Z',
  ...overrides,
})


describe('OrderStatusHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // =========================================================================
  // AC-007: Section title
  // =========================================================================

  describe('AC-007: Section title display', () => {
    it('displays "ステータス履歴" section title', () => {
      mockUseSWR.mockReturnValue({
        data: { items: [createMockHistoryItem()] },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      expect(screen.getByText('ステータス履歴')).toBeInTheDocument()
    })

    it('displays section title even when loading', () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      expect(screen.getByText('ステータス履歴')).toBeInTheDocument()
    })
  })

  // =========================================================================
  // AC-008: History items display
  // =========================================================================

  describe('AC-008: History items display', () => {
    it('displays change date/time for each history record', () => {
      const historyItems = [
        createMockHistoryItem({
          id: 'history-1',
          from_status: 'ordered',
          to_status: 'manufacturing',
          changed_by: 'Admin User',
          created_at: '2026-01-15T10:30:00Z',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      // Should display the date in some formatted way
      // The exact format depends on implementation, but the date info should be present
      expect(screen.getByText(/2026/)).toBeInTheDocument()
    })

    it('displays from_status and to_status badges in Japanese', () => {
      const historyItems = [
        createMockHistoryItem({
          from_status: 'ordered',
          to_status: 'manufacturing',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      // Japanese labels for statuses
      expect(screen.getByText('発注中')).toBeInTheDocument()
      expect(screen.getByText('製造中')).toBeInTheDocument()
    })

    it('displays changed_by name for each record', () => {
      const historyItems = [
        createMockHistoryItem({
          changed_by: 'テスト管理者',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      expect(screen.getByText('テスト管理者')).toBeInTheDocument()
    })

    it('displays multiple history records', () => {
      const historyItems = [
        createMockHistoryItem({
          id: 'history-2',
          from_status: 'manufacturing',
          to_status: 'delivered',
          changed_by: 'Admin 1',
          created_at: '2026-01-16T10:30:00Z',
        }),
        createMockHistoryItem({
          id: 'history-1',
          from_status: 'ordered',
          to_status: 'manufacturing',
          changed_by: 'Admin 2',
          created_at: '2026-01-15T10:30:00Z',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      expect(screen.getByText('Admin 1')).toBeInTheDocument()
      expect(screen.getByText('Admin 2')).toBeInTheDocument()
    })

    it('displays all status types correctly in Japanese', () => {
      const historyItems = [
        createMockHistoryItem({
          id: 'history-3',
          from_status: 'delivered',
          to_status: 'shipped',
          created_at: '2026-01-17T10:30:00Z',
        }),
        createMockHistoryItem({
          id: 'history-2',
          from_status: 'manufacturing',
          to_status: 'delivered',
          created_at: '2026-01-16T10:30:00Z',
        }),
        createMockHistoryItem({
          id: 'history-1',
          from_status: null,
          to_status: 'ordered',
          created_at: '2026-01-15T10:30:00Z',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      // Verify Japanese labels exist
      expect(screen.getByText('発送完了')).toBeInTheDocument()
      // '納入済' appears as both from_status (history-3) and to_status (history-2)
      expect(screen.getAllByText('納入済')).toHaveLength(2)
    })
  })

  // =========================================================================
  // AC-009: Empty state
  // =========================================================================

  describe('AC-009: Empty state', () => {
    it('displays empty message when no history exists', () => {
      mockUseSWR.mockReturnValue({
        data: { items: [] },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      expect(screen.getByText('ステータス変更履歴はありません')).toBeInTheDocument()
    })
  })

  // =========================================================================
  // Additional edge cases
  // =========================================================================

  describe('Edge cases', () => {
    it('handles null from_status (initial order creation)', () => {
      const historyItems = [
        createMockHistoryItem({
          from_status: null,
          to_status: 'ordered',
          changed_by: 'system',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      // Should render without error and show the target status
      expect(screen.getByText('発注中')).toBeInTheDocument()
    })

    it('handles null changed_by gracefully', () => {
      const historyItems = [
        createMockHistoryItem({
          changed_by: null,
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: historyItems },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      // Should render without error
      expect(screen.getByText('ステータス履歴')).toBeInTheDocument()
    })

    it('shows loading state', () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderStatusHistory orderId="order-123" />)

      // Component should render section title while loading
      expect(screen.getByText('ステータス履歴')).toBeInTheDocument()
    })
  })
})
