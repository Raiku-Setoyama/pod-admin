/**
 * /settings/order-sources ページのテスト
 *
 * FEAT-0014: 受注元管理CRUD
 *
 * - AC-017: サイドバーに「受注元」メニューが表示される
 * - AC-018: /settings/order-sources にアクセスすると受注元管理ページが表示される
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import SettingsOrderSourcesPage from '@/app/(dashboard)/settings/order-sources/page'
import { Sidebar } from '@/components/layout/sidebar'
import type { User } from '@/types/api'

// SWR をモック
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: { items: [], total: 0, page: 1, limit: 20 },
    error: undefined,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
  })),
}))

// API クライアントをモック
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(() => Promise.resolve({})),
}))

// useCurrentUser をモック
vi.mock('@/features/auth/hooks/use-current-user', () => ({
  useCurrentUser: vi.fn(),
}))

import { useCurrentUser } from '@/features/auth/hooks/use-current-user'

const mockUseCurrentUser = vi.mocked(useCurrentUser)

describe('Settings Order Sources Page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('AC-018: /settings/order-sources にアクセスすると受注元管理ページが表示される', () => {
    it('受注元管理ページが正常にレンダリングされる', () => {
      render(<SettingsOrderSourcesPage />)

      // ページが正常に表示されること（受注元に関連するテキストが存在）
      expect(screen.getByText(/受注元/)).toBeInTheDocument()
    })

    it('受注元一覧コンポーネントが含まれている', () => {
      render(<SettingsOrderSourcesPage />)

      // 新規登録ボタンが表示されること（OrderSourceList が含まれている証拠）
      expect(screen.getByRole('button', { name: /新規登録|新規|追加/ })).toBeInTheDocument()
    })
  })

  describe('AC-017: サイドバーに「受注元」メニューが表示される', () => {
    it('サイドバーに「受注元」メニューリンクが表示される', () => {
      const mockUser: User = {
        id: 'user-123',
        email: 'admin@example.com',
        name: 'Admin User',
        role: 'admin',
        is_active: true,
      }

      mockUseCurrentUser.mockReturnValue({
        user: mockUser,
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      })

      render(<Sidebar />)

      // 「受注元」メニューが表示されること
      expect(screen.getByText('受注元')).toBeInTheDocument()
    })

    it('「受注元」メニューが /order-sources へのリンクを持つ', () => {
      const mockUser: User = {
        id: 'user-123',
        email: 'admin@example.com',
        name: 'Admin User',
        role: 'admin',
        is_active: true,
      }

      mockUseCurrentUser.mockReturnValue({
        user: mockUser,
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      })

      render(<Sidebar />)

      // 受注元リンクが /order-sources を指していること
      const orderSourceLink = screen.getByText('受注元').closest('a')
      expect(orderSourceLink).toHaveAttribute('href', '/order-sources')
    })
  })
})
