/**
 * OrderSourceFormDialog コンポーネントのテスト
 *
 * FEAT-0014: 受注元管理CRUD
 *
 * - AC-014: 新規登録ダイアログを開いて受注元を登録できる
 * - AC-015: 編集ダイアログを開いて受注元を編集できる
 * - AC-019: 受注元フォームのバリデーションが動作する
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { OrderSourceFormDialog } from '@/features/order-sources/components/order-source-form-dialog'
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

describe('OrderSourceFormDialog', () => {
  const mockOnSuccess = vi.fn()
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('ダイアログ表示', () => {
    it('open=true でダイアログが表示される', () => {
      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('open=false でダイアログが表示されない', () => {
      render(
        <OrderSourceFormDialog
          open={false}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('新規登録時は「受注元登録」のタイトルが表示される', () => {
      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByText(/受注元登録|新規登録|受注元を追加/)).toBeInTheDocument()
    })

    it('編集時は「受注元編集」のタイトルが表示される', () => {
      const existingSource = createMockOrderSource()
      render(
        <OrderSourceFormDialog
          open={true}
          orderSource={existingSource}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByText(/受注元編集|編集/)).toBeInTheDocument()
    })
  })

  describe('AC-014: 新規登録ダイアログ', () => {
    it('必要な入力フィールドが全て表示される', () => {
      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // 必須フィールドのラベルまたはプレースホルダーが存在すること
      expect(screen.getByLabelText(/受注元コード|コード/)).toBeInTheDocument()
      expect(screen.getByLabelText(/受注元名|名前|名称/)).toBeInTheDocument()
      expect(screen.getByLabelText(/APIキー|API キー/)).toBeInTheDocument()
      expect(screen.getByLabelText(/電話番号/)).toBeInTheDocument()
      expect(screen.getByLabelText(/郵便番号/)).toBeInTheDocument()
      expect(screen.getByLabelText(/都道府県/)).toBeInTheDocument()
      expect(screen.getByLabelText(/市区町村/)).toBeInTheDocument()
    })

    it('保存ボタンが表示される', () => {
      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      expect(screen.getByRole('button', { name: /保存|登録|作成/ })).toBeInTheDocument()
    })

    it('フォーム送信時にPOST APIが呼ばれる', async () => {
      const user = userEvent.setup()
      mockApiClient.mockResolvedValueOnce({
        id: 'new-source',
        code: 'NEW01',
        name: '新規受注元',
      })

      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // フォームに入力
      await user.type(screen.getByLabelText(/受注元コード|コード/), 'NEW01')
      await user.type(screen.getByLabelText(/受注元名|名前|名称/), '新規受注元')
      await user.type(screen.getByLabelText(/APIキー|API キー/), 'new-api-key')
      await user.type(screen.getByLabelText(/電話番号/), '03-0000-0000')
      await user.type(screen.getByLabelText(/郵便番号/), '100-0001')
      await user.type(screen.getByLabelText(/都道府県/), '東京都')
      await user.type(screen.getByLabelText(/市区町村/), '千代田区')

      // 保存ボタンをクリック
      const submitButton = screen.getByRole('button', { name: /保存|登録|作成/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/order-sources'),
          expect.objectContaining({
            method: 'POST',
          })
        )
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })
  })

  describe('AC-015: 編集ダイアログ', () => {
    it('既存データがフォームにプリセットされる', () => {
      const existingSource = createMockOrderSource({
        code: 'EXIST',
        name: '既存受注元',
        phone: '03-9999-8888',
      })

      render(
        <OrderSourceFormDialog
          open={true}
          orderSource={existingSource}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // 既存のデータが入力フィールドに表示されること
      expect(screen.getByDisplayValue('EXIST')).toBeInTheDocument()
      expect(screen.getByDisplayValue('既存受注元')).toBeInTheDocument()
      expect(screen.getByDisplayValue('03-9999-8888')).toBeInTheDocument()
    })

    it('編集時にPATCH APIが呼ばれる', async () => {
      const user = userEvent.setup()
      const existingSource = createMockOrderSource({ id: 'source-001' })
      mockApiClient.mockResolvedValueOnce({
        ...existingSource,
        name: '更新後の名前',
      })

      render(
        <OrderSourceFormDialog
          open={true}
          orderSource={existingSource}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // 名前フィールドを変更
      const nameInput = screen.getByLabelText(/受注元名|名前|名称/)
      await user.clear(nameInput)
      await user.type(nameInput, '更新後の名前')

      // 保存ボタンをクリック
      const submitButton = screen.getByRole('button', { name: /保存|更新/ })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockApiClient).toHaveBeenCalledWith(
          expect.stringContaining('/order-sources/source-001'),
          expect.objectContaining({
            method: 'PATCH',
          })
        )
        expect(mockOnSuccess).toHaveBeenCalled()
      })
    })
  })

  describe('AC-019: フォームバリデーション', () => {
    it('必須項目を空のまま保存しようとするとバリデーションエラーが表示される', async () => {
      const user = userEvent.setup()

      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      // 何も入力せずに保存ボタンをクリック
      const submitButton = screen.getByRole('button', { name: /保存|登録|作成/ })
      await user.click(submitButton)

      // バリデーションエラーが表示されること
      await waitFor(() => {
        // 必須フィールドのエラーメッセージが表示される
        const errorMessages = screen.getAllByText(/必須|入力してください|required/i)
        expect(errorMessages.length).toBeGreaterThan(0)
      })

      // APIが呼ばれないこと
      expect(mockApiClient).not.toHaveBeenCalled()
    })
  })

  describe('キャンセルボタン', () => {
    it('キャンセルボタンでダイアログが閉じる', async () => {
      const user = userEvent.setup()

      render(
        <OrderSourceFormDialog
          open={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      )

      const cancelButton = screen.getByRole('button', { name: /キャンセル|閉じる|戻る/ })
      await user.click(cancelButton)

      expect(mockOnClose).toHaveBeenCalled()
    })
  })
})
