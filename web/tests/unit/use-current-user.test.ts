import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useCurrentUser } from '@/features/auth/hooks/use-current-user'
import type { User } from '@/types/api'

// SWRをモック
vi.mock('swr', () => ({
  default: vi.fn(),
}))

// APIクライアントをモック
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

import useSWR from 'swr'
import { apiClient } from '@/lib/api/client'

const mockUseSWR = vi.mocked(useSWR)
const mockApiClient = vi.mocked(apiClient)

describe('useCurrentUser', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.resetAllMocks()
  })

  describe('AC-002: useCurrentUserフックがユーザー情報を正しく取得する', () => {
    it('有効なaccess_tokenがある場合、APIからユーザー情報（email, name, role）を取得し返却する', async () => {
      const mockUser: User = {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'admin',
        is_active: true,
      }

      mockUseSWR.mockReturnValue({
        data: mockUser,
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      })

      const { result } = renderHook(() => useCurrentUser())

      expect(result.current.user).toEqual(mockUser)
      expect(result.current.user?.email).toBe('test@example.com')
      expect(result.current.user?.name).toBe('Test User')
      expect(result.current.user?.role).toBe('admin')
    })

    it('SWRが /auth/me エンドポイントをfetcherに渡して呼び出される', () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      })

      renderHook(() => useCurrentUser())

      expect(mockUseSWR).toHaveBeenCalledWith(
        '/auth/me',
        expect.any(Function)
      )
    })
  })

  describe('AC-003: API呼び出し中はローディング状態となる', () => {
    it('レスポンスを待っている間、isLoading=trueとなる', () => {
      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: true,
        isValidating: false,
        mutate: vi.fn(),
      })

      const { result } = renderHook(() => useCurrentUser())

      expect(result.current.isLoading).toBe(true)
      expect(result.current.user).toBeUndefined()
    })

    it('データ取得完了後、isLoading=falseとなる', () => {
      const mockUser: User = {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'admin',
        is_active: true,
      }

      mockUseSWR.mockReturnValue({
        data: mockUser,
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      })

      const { result } = renderHook(() => useCurrentUser())

      expect(result.current.isLoading).toBe(false)
      expect(result.current.user).toBeDefined()
    })
  })

  describe('AC-004: API呼び出しエラー時はエラー状態となる', () => {
    it('無効なトークンまたはAPI障害時、isError=trueとなる', () => {
      const mockError = new Error('Unauthorized')

      mockUseSWR.mockReturnValue({
        data: undefined,
        error: mockError,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      })

      const { result } = renderHook(() => useCurrentUser())

      expect(result.current.error).toBeDefined()
      expect(result.current.user).toBeUndefined()
    })

    it('エラー時、errorオブジェクトが返却される', () => {
      const mockError = new Error('Network Error')

      mockUseSWR.mockReturnValue({
        data: undefined,
        error: mockError,
        isLoading: false,
        isValidating: false,
        mutate: vi.fn(),
      })

      const { result } = renderHook(() => useCurrentUser())

      expect(result.current.error).toEqual(mockError)
    })
  })

  describe('フックの戻り値の構造', () => {
    it('user, isLoading, error, mutate を返す', () => {
      const mockMutate = vi.fn()

      mockUseSWR.mockReturnValue({
        data: undefined,
        error: undefined,
        isLoading: false,
        isValidating: false,
        mutate: mockMutate,
      })

      const { result } = renderHook(() => useCurrentUser())

      expect(result.current).toHaveProperty('user')
      expect(result.current).toHaveProperty('isLoading')
      expect(result.current).toHaveProperty('error')
      expect(result.current).toHaveProperty('mutate')
    })
  })
})
