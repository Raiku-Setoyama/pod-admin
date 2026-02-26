import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { isTokenExpired } from '@/lib/api/client'

// JWTトークンを生成するヘルパー関数
function createMockJwt(payload: { exp?: number }): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const body = btoa(JSON.stringify(payload))
  const signature = 'mock-signature'
  return `${header}.${body}.${signature}`
}

describe('Token Refresh Utilities', () => {
  describe('isTokenExpired', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('should return true when token is null', () => {
      expect(isTokenExpired(null)).toBe(true)
    })

    it('should return true when token is empty string', () => {
      expect(isTokenExpired('')).toBe(true)
    })

    it('should return true when token is invalid format', () => {
      expect(isTokenExpired('invalid-token')).toBe(true)
      expect(isTokenExpired('only.two.parts.extra')).toBe(true)
    })

    it('should return true when token has no exp claim', () => {
      const token = createMockJwt({ })
      expect(isTokenExpired(token)).toBe(true)
    })

    it('should return true when token is expired', () => {
      // 現在時刻: 2024-01-01 00:00:00 UTC
      vi.setSystemTime(new Date('2024-01-01T00:00:00Z'))

      // 有効期限: 2023-12-31 23:59:00 UTC (1分前に期限切れ)
      const expiredTime = Math.floor(new Date('2023-12-31T23:59:00Z').getTime() / 1000)
      const token = createMockJwt({ exp: expiredTime })

      expect(isTokenExpired(token)).toBe(true)
    })

    it('should return true when token expires within buffer time', () => {
      // 現在時刻: 2024-01-01 00:00:00 UTC
      vi.setSystemTime(new Date('2024-01-01T00:00:00Z'))

      // 有効期限: 2024-01-01 00:00:30 UTC (30秒後に期限切れ、60秒バッファ内)
      const expiresSoon = Math.floor(new Date('2024-01-01T00:00:30Z').getTime() / 1000)
      const token = createMockJwt({ exp: expiresSoon })

      expect(isTokenExpired(token, 60)).toBe(true)
    })

    it('should return false when token is valid and not within buffer', () => {
      // 現在時刻: 2024-01-01 00:00:00 UTC
      vi.setSystemTime(new Date('2024-01-01T00:00:00Z'))

      // 有効期限: 2024-01-01 00:10:00 UTC (10分後に期限切れ、60秒バッファ外)
      const validTime = Math.floor(new Date('2024-01-01T00:10:00Z').getTime() / 1000)
      const token = createMockJwt({ exp: validTime })

      expect(isTokenExpired(token, 60)).toBe(false)
    })

    it('should use default buffer of 60 seconds', () => {
      vi.setSystemTime(new Date('2024-01-01T00:00:00Z'))

      // 有効期限: 2024-01-01 00:00:59 UTC (59秒後、デフォルト60秒バッファ内)
      const expiresSoon = Math.floor(new Date('2024-01-01T00:00:59Z').getTime() / 1000)
      const token = createMockJwt({ exp: expiresSoon })

      expect(isTokenExpired(token)).toBe(true)

      // 有効期限: 2024-01-01 00:01:01 UTC (61秒後、デフォルト60秒バッファ外)
      const validTime = Math.floor(new Date('2024-01-01T00:01:01Z').getTime() / 1000)
      const validToken = createMockJwt({ exp: validTime })

      expect(isTokenExpired(validToken)).toBe(false)
    })

    it('should handle custom buffer time', () => {
      vi.setSystemTime(new Date('2024-01-01T00:00:00Z'))

      // 有効期限: 2024-01-01 00:02:00 UTC (2分後)
      const expiresIn2Min = Math.floor(new Date('2024-01-01T00:02:00Z').getTime() / 1000)
      const token = createMockJwt({ exp: expiresIn2Min })

      // 60秒バッファ → 有効
      expect(isTokenExpired(token, 60)).toBe(false)

      // 180秒バッファ → 期限切れ扱い
      expect(isTokenExpired(token, 180)).toBe(true)
    })
  })
})
