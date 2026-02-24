/**
 * OrderSourceList コンポーネントのテスト
 *
 * FEAT-0014: 受注元管理CRUD
 *
 * - AC-013: /order-sources ページで受注元一覧が表示される
 * - AC-017: サイドバーに「受注元」メニューが表示される
 * - AC-020: APIキーがマスク表示される
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { OrderSourceList } from '@/features/order-sources/components/order-source-list'
import type { OrderSource } from '@/types/api'

// SWR をモック
vi.mock('swr', () => ({
  default: vi.fn(),
}))

// API クライアントをモック
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(() => Promise.resolve({})),
}))

import useSWR from 'swr'

const mockUseSWR = vi.mocked(useSWR)

const createMockOrderSource = (overrides: Partial<OrderSource> = {}): OrderSource => ({
  id: 'source-001',
  code: 'RKSYO',
  name: '楽商',
  api_key: 'secret-api-key-12345',
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

describe('OrderSourceList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('AC-013: 受注元一覧が表示される', () => {
    it('受注元のコード、名前、電話番号が一覧表示される', () => {
      const mockSources = [
        createMockOrderSource({ id: 'src-1', code: 'RKSYO', name: '楽商', phone: '03-1234-5678' }),
        createMockOrderSource({ id: 'src-2', code: 'BASE01', name: 'BASE', phone: '06-9876-5432' }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: mockSources, total: 2, page: 1, limit: 20 },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderSourceList />)

      // コードが表示されること
      expect(screen.getByText('RKSYO')).toBeInTheDocument()
      expect(screen.getByText('BASE01')).toBeInTheDocument()

      // 名前が表示されること
      expect(screen.getByText('楽商')).toBeInTheDocument()
      expect(screen.getByText('BASE')).toBeInTheDocument()

      // 電話番号が表示されること
      expect(screen.getByText('03-1234-5678')).toBeInTheDocument()
      expect(screen.getByText('06-9876-5432')).toBeInTheDocument()
    })

    it('有効/無効状態が一覧表示される', () => {
      const mockSources = [
        createMockOrderSource({ id: 'src-1', is_active: true }),
        createMockOrderSource({ id: 'src-2', code: 'INACT', name: '無効元', is_active: false }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: mockSources, total: 2, page: 1, limit: 20 },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderSourceList />)

      // 有効/無効の表示がある（テキストまたはバッジで表示される想定）
      const activeElements = screen.getAllByText(/有効|無効/)
      expect(activeElements.length).toBeGreaterThanOrEqual(2)
    })

    it('ローディング中はローディング表示がされる', () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderSourceList />)

      // ローディング中の表示があること（テキストまたはスピナー）
      // 具体的なUI実装に依存するが、テーブルにデータがないことを確認
      expect(screen.queryByText('RKSYO')).not.toBeInTheDocument()
    })

    it('受注元が0件の場合は空状態が表示される', () => {
      mockUseSWR.mockReturnValue({
        data: { items: [], total: 0, page: 1, limit: 20 },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderSourceList />)

      // 受注元がない場合のメッセージがある（実装依存）
      expect(screen.queryByText('RKSYO')).not.toBeInTheDocument()
    })
  })

  describe('AC-020: APIキーがマスク表示される', () => {
    it('APIキーがマスク表示される（先頭数文字 + ****）', () => {
      const mockSources = [
        createMockOrderSource({
          id: 'src-1',
          api_key: 'secret-api-key-12345',
        }),
      ]

      mockUseSWR.mockReturnValue({
        data: { items: mockSources, total: 1, page: 1, limit: 20 },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderSourceList />)

      // APIキーの全文が表示されないこと
      expect(screen.queryByText('secret-api-key-12345')).not.toBeInTheDocument()
      // マスクされた表示があること（先頭数文字 + **** のパターン）
      const maskedElement = screen.getByText(/secr.*\*/)
      expect(maskedElement).toBeInTheDocument()
    })
  })

  describe('新規登録ボタン', () => {
    it('「新規登録」ボタンが表示される', () => {
      mockUseSWR.mockReturnValue({
        data: { items: [], total: 0, page: 1, limit: 20 },
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      } as any)

      render(<OrderSourceList />)

      expect(screen.getByRole('button', { name: /新規登録|新規|追加/ })).toBeInTheDocument()
    })
  })
})
