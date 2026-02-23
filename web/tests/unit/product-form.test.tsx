/**
 * ProductForm のテスト
 *
 * FEAT-0002: 商品種別を5種類に限定（マグカップ削除）
 *
 * このテストは、商品フォームに許可された5種類のみが表示され、
 * マグカップが削除されていることを検証します。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { ProductForm } from '@/features/products/components/product-form'

// SWR をモック
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: { items: [] },
    error: null,
    isLoading: false,
  })),
}))

// API クライアントをモック
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(() => Promise.resolve({})),
}))

describe('ProductForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('商品種別オプションの検証', () => {
    it('商品種別セレクトボックスに5種類のみ表示される', () => {
      render(<ProductForm />)

      // Radix UIのSelect は hidden の native select を持つ
      // その中のオプションを取得して検証
      const hiddenSelects = document.querySelectorAll('select[aria-hidden="true"]')
      // 最初の hidden select が商品種別
      const productTypeSelect = hiddenSelects[0]

      expect(productTypeSelect).toBeDefined()

      const options = productTypeSelect.querySelectorAll('option')
      const optionTexts = Array.from(options).map((opt) => opt.textContent)

      // 許可された5種類が表示されることを確認
      expect(optionTexts).toContain('アクリルキーホルダー')
      expect(optionTexts).toContain('アクリルスタンド')
      expect(optionTexts).toContain('ステッカー')
      expect(optionTexts).toContain('トートバッグ')
      expect(optionTexts).toContain('Tシャツ')
    })

    it('商品種別セレクトボックスにマグカップが表示されない', () => {
      render(<ProductForm />)

      // Radix UIのSelect は hidden の native select を持つ
      const hiddenSelects = document.querySelectorAll('select[aria-hidden="true"]')
      const productTypeSelect = hiddenSelects[0]

      expect(productTypeSelect).toBeDefined()

      const options = productTypeSelect.querySelectorAll('option')
      const optionTexts = Array.from(options).map((opt) => opt.textContent)

      // マグカップが表示されないことを確認
      expect(optionTexts).not.toContain('マグカップ')
    })

    it('商品種別の選択肢が正確に5つである', () => {
      render(<ProductForm />)

      // Radix UIのSelect は hidden の native select を持つ
      const hiddenSelects = document.querySelectorAll('select[aria-hidden="true"]')
      const productTypeSelect = hiddenSelects[0]

      expect(productTypeSelect).toBeDefined()

      const options = productTypeSelect.querySelectorAll('option')

      // 選択肢が正確に5つであることを確認
      expect(options).toHaveLength(5)
    })
  })

  describe('productTypes配列の検証', () => {
    it('productTypes配列にマグカップが含まれていない', async () => {
      // product-form.tsx から productTypes をインポートできないため
      // レンダリング結果から間接的に検証
      render(<ProductForm />)

      // 「マグカップ」というテキストがドキュメント内に存在しないことを確認
      expect(screen.queryByText('マグカップ')).not.toBeInTheDocument()
    })
  })
})
