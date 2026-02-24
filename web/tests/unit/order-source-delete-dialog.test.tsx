/**
 * OrderSourceDeleteDialog コンポーネントのテスト
 *
 * FEAT-0014: 受注元管理CRUD
 *
 * - AC-016: 受注元一覧ページから削除確認ダイアログを開いて受注元を削除できる
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OrderSourceDeleteDialog } from '@/features/order-sources/components/order-source-delete-dialog'
import type { OrderSource } from '@/types/api'

// API クライアントをモック
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(() => Promise.resolve({})),
}))

import { apiClient } from '@/lib/api/client'

const mockApiClient = vi.mocked(apiClient)

const createMockOrderSource = (overrides: Partial<OrderSource> = {}): OrderSource => ({
  id: 'source-001',
  code: 'RKSYO',
  name: '楽商',
  api_key: 'test-api-key-001',
  phone: '03-1234-5678',
  postal_code: '100-0001',
  address_prefecture: '東京都',
  address_city: '千代田区1-1-1',
  address_building: null,
  is_active: true,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
})

describe('OrderSourceDeleteDialog', () => {
  const mockOnSuccess = vi.fn()
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('ダイアログ表示', () => {
    it('open=true で削除確認ダイアログが表示される', () => {
      const source = createMockOrderSource()

      render(
        <OrderSourceDeleteDialog
          open={true}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('open=false でダイアログが表示されない', () => {
      const source = createMockOrderSource()

      render(
        <OrderSourceDeleteDialog
          open={false}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('削除確認メッセージに受注元名が含まれる', () => {
      const source = createMockOrderSource({ name: '楽商' })

      render(
        <OrderSourceDeleteDialog
          open={true}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // 受注元名を含む確認メッセージが表示される
      expect(screen.getByText(/楽商/)).toBeInTheDocument()
      expect(screen.getByText(/削除/)).toBeInTheDocument()
    })
  })

  describe('AC-016: 削除確認ダイアログで削除できる', () => {
    it('「削除」ボタンをクリックするとDELETE APIが呼ばれる', async () => {
      const user = userEvent.setup()
      const source = createMockOrderSource({ id: 'source-to-delete' })
      mockApiClient.mockResolvedValueOnce({})

      render(
        <OrderSourceDeleteDialog
          open={true}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // 削除ボタンをクリック
      const deleteButton = screen.getByRole('button', { name: /削除/ })
      await user.click(deleteButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/order-sources/source-to-delete'),
          expect.objectContaining({
            method: 'DELETE',
          })
        )
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })

    it('削除中はローディング表示がされる', async () => {
      const user = userEvent.setup()
      const source = createMockOrderSource()

      // APIコールをハングさせる
      mockApiClient.mockImplementationOnce(() => new Promise(() => {}))

      render(
        <OrderSourceDeleteDialog
          open={true}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const deleteButton = screen.getByRole('button', { name: /削除/ })
      await user.click(deleteButton)

      await waitFor(() => {
        // ローディング状態の表示（ボタンテキストの変化やスピナー）
        expect(screen.getByText(/削除中|処理中/)).toBeInTheDocument()
      })
    })

    it('削除エラー時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup()
      const source = createMockOrderSource()
      mockApiClient.mockRejectedValueOnce(new Error('Server error'))

      render(
        <OrderSourceDeleteDialog
          open={true}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const deleteButton = screen.getByRole('button', { name: /削除/ })
      await user.click(deleteButton)

      await waitFor(() => {
        expect(screen.getByText(/エラー|失敗|Server error/)).toBeInTheDocument()
      })
    })
  })

  describe('キャンセル操作', () => {
    it('キャンセルボタンでダイアログが閉じる', async () => {
      const user = userEvent.setup()
      const source = createMockOrderSource()

      render(
        <OrderSourceDeleteDialog
          open={true}
          orderSource={source}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const cancelButton = screen.getByRole('button', { name: /キャンセル/ })
      await user.click(cancelButton)

      expect(mockOnClose).toHaveBeenCalled()
      // APIが呼ばれないこと
      expect(mockApiClient).not.toHaveBeenCalled()
    })
  })
})
