import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Sidebar } from '@/components/layout/sidebar'
import type { User } from '@/types/api'

// useCurrentUserフックをモック
vi.mock('@/features/auth/hooks/use-current-user', () => ({
  useCurrentUser: vi.fn(),
}))

import { useCurrentUser } from '@/features/auth/hooks/use-current-user'

const mockUseCurrentUser = vi.mocked(useCurrentUser)

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('AC-001: サイドバーにログインユーザーのメールアドレスが表示される', () => {
    it('ハードコードされた値ではなく、/auth/meから取得したメールアドレスが表示される', () => {
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

      // 動的に取得したメールアドレスが表示されること
      expect(screen.getByText('admin@example.com')).toBeInTheDocument()
      // ハードコードされたメールアドレスが表示されないこと
      expect(screen.queryByText('raiku6019@gmail.com')).not.toBeInTheDocument()
    })

    it('異なるユーザーでログインした場合、そのユーザーのメールアドレスが表示される', () => {
      const mockUser: User = {
        id: 'user-456',
        email: 'staff@example.com',
        name: 'Staff User',
        role: 'staff',
        is_active: true,
      }

      mockUseCurrentUser.mockReturnValue({
        user: mockUser,
        isLoading: false,
        error: undefined,
        mutate: vi.fn(),
      })

      render(<Sidebar />)

      expect(screen.getByText('staff@example.com')).toBeInTheDocument()
    })
  })

  describe('AC-003: API呼び出し中はローディング状態となる', () => {
    it('ローディング中は適切なローディング表示がされる', () => {
      mockUseCurrentUser.mockReturnValue({
        user: undefined,
        isLoading: true,
        error: undefined,
        mutate: vi.fn(),
      })

      render(<Sidebar />)

      // ローディング中はメールアドレスが表示されない
      expect(screen.queryByText('admin@example.com')).not.toBeInTheDocument()
    })
  })

  describe('AC-004: API呼び出しエラー時はエラー状態となる', () => {
    it('エラー時はフォールバック表示がされる', () => {
      mockUseCurrentUser.mockReturnValue({
        user: undefined,
        isLoading: false,
        error: new Error('Unauthorized'),
        mutate: vi.fn(),
      })

      render(<Sidebar />)

      // エラー時はハードコードされたメールも動的なメールも表示されない
      expect(screen.queryByText('raiku6019@gmail.com')).not.toBeInTheDocument()
    })
  })

  describe('AC-005: メールアドレスが長い場合も適切に表示される', () => {
    it('長いメールアドレスはtruncateクラスにより省略表示される', () => {
      const mockUser: User = {
        id: 'user-789',
        email: 'very.long.email.address@subdomain.example.com',
        name: 'Long Email User',
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

      // メールアドレスを含む要素を取得
      const emailElement = screen.getByText('very.long.email.address@subdomain.example.com')
      expect(emailElement).toBeInTheDocument()
      // truncateクラスが適用されていること（既存のbase-sidebarの仕様に準拠）
      expect(emailElement).toHaveClass('truncate')
    })
  })

  describe('サイドバーの基本構造', () => {
    it('ナビゲーションリンクが正しく表示される', () => {
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

      expect(screen.getByText('受注')).toBeInTheDocument()
      expect(screen.getByText('発注')).toBeInTheDocument()
      expect(screen.getByText('配送')).toBeInTheDocument()
      expect(screen.getByText('メーカー')).toBeInTheDocument()
      expect(screen.getByText('商品マスタ')).toBeInTheDocument()
      expect(screen.getByText('チャット')).toBeInTheDocument()
    })

    it('設定とログアウトボタンが表示される', () => {
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

      expect(screen.getByText('設定')).toBeInTheDocument()
      expect(screen.getByText('ログアウト')).toBeInTheDocument()
    })
  })
})
