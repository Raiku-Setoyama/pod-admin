/**
 * Issue #79: 発注明細CSV（すべての発注ページ）の「商品タイプ」列を、発注リストと同じ
 * 「{商品種類} - {サイズ} - {位置} - {色}」形式（半角 " - " 区切り、空要素はスキップ）に統一する。
 *
 * 対象: web/src/app/(dashboard)/purchase-orders/all/page.tsx の handleExportCSV
 *
 * 検証方法: ページを描画して「CSVダウンロード」を押下し、生成された Blob を
 * URL.createObjectURL のモック経由で取得して中身を検証する。
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock API client (page imports it at module level)
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

// Mock SWR (indirectly used by the hooks)
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: undefined,
    error: undefined,
    isLoading: false,
    isValidating: false,
    mutate: vi.fn(),
  })),
}))

// Mock sonner toast
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

// Mock data hooks
vi.mock('@/features/purchase-orders/hooks/use-manufacturer-orders', () => ({
  useAllManufacturerOrderItems: vi.fn(),
}))

vi.mock('@/features/manufacturers/hooks/use-manufacturers', () => ({
  useManufacturers: vi.fn(),
}))

import { useAllManufacturerOrderItems } from '@/features/purchase-orders/hooks/use-manufacturer-orders'
import { useManufacturers } from '@/features/manufacturers/hooks/use-manufacturers'

// ======================================
// Mock data
// ======================================

interface MockOrderItem {
  id: string
  order_id: string
  order_number: string
  uid: string | null
  product_id: string
  product_name: string
  product_type: string
  price: number
  quantity: number
  size: string | null
  position: string | null
  color: string | null
  design_image_url: string | null
  thumbnail_image_url: string | null
  ordered_at: string
  customer_name: string
  status: string
  manufacturer_id: string
  manufacturer_name: string
  lead_time_days: number
  expected_delivery_date: string
}

function makeItem(overrides: Partial<MockOrderItem>): MockOrderItem {
  return {
    id: 'item-x',
    order_id: 'order-x',
    order_number: 'ORD-X',
    uid: 'UID-X',
    product_id: 'prod-x',
    product_name: '商品',
    product_type: 'tshirt',
    price: 1000,
    quantity: 1,
    size: null,
    position: null,
    color: null,
    design_image_url: null,
    thumbnail_image_url: null,
    ordered_at: '2026-01-15T10:00:00Z',
    customer_name: '顧客',
    status: 'ordered',
    manufacturer_id: 'mfr-1',
    manufacturer_name: 'メーカーA',
    lead_time_days: 7,
    expected_delivery_date: '2026-01-22',
    ...overrides,
  }
}

const MOCK_ITEMS: MockOrderItem[] = [
  // 種類・サイズ・位置・色すべてあり
  makeItem({ id: 'i1', product_type: 'tshirt', size: 'M', position: '正面', color: '白' }),
  // 位置なし（空要素スキップ）
  makeItem({ id: 'i2', product_type: 'sticker', size: '100x100mm', position: null, color: 'ホワイト' }),
  // acrylic_stand → アクリルフィギュア
  makeItem({ id: 'i3', product_type: 'acrylic_stand', size: '100mm', position: null, color: 'クリア' }),
  // 属性なし（種類名のみ）
  makeItem({ id: 'i4', product_type: 'acrylic_keychain', size: null, position: null, color: null }),
]

// The generated CSV string, captured from the Blob constructor (jsdom's Blob
// does not implement .text(), so we read the constructor parts directly).
let capturedCsv = ''
const OriginalBlob = globalThis.Blob

/** ページを描画し「CSVダウンロード」を押して、生成されたCSV文字列を返す。 */
async function exportCsvText(): Promise<string> {
  const user = userEvent.setup()
  const { default: AllPurchaseOrdersPage } = await import(
    '@/app/(dashboard)/purchase-orders/all/page'
  )

  render(<AllPurchaseOrdersPage />)

  const button = screen.getByRole('button', { name: /CSVダウンロード/ })
  await user.click(button)

  expect(URL.createObjectURL).toHaveBeenCalledTimes(1)
  return capturedCsv
}

describe('Issue #79: 発注明細CSVの「商品タイプ」列を発注リスト形式に統一', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    capturedCsv = ''

    vi.mocked(useAllManufacturerOrderItems).mockReturnValue({
      data: {
        items: MOCK_ITEMS,
        total: MOCK_ITEMS.length,
        total_quantity: 4,
        total_amount: 4000,
      },
      isLoading: false,
      isFiltering: false,
      error: undefined,
      mutate: vi.fn(),
    } as unknown as ReturnType<typeof useAllManufacturerOrderItems>)

    vi.mocked(useManufacturers).mockReturnValue({
      manufacturers: [],
      isLoading: false,
      error: undefined,
      mutate: vi.fn(),
    } as unknown as ReturnType<typeof useManufacturers>)

    // Capture CSV content from the Blob parts; jsdom's Blob lacks .text().
    vi.stubGlobal(
      'Blob',
      class MockBlob extends OriginalBlob {
        constructor(parts: BlobPart[] = [], options?: BlobPropertyBag) {
          super(parts, options)
          capturedCsv = parts
            .map((p) => (typeof p === 'string' ? p : ''))
            .join('')
        }
      }
    )
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()

    // Prevent jsdom from attempting to navigate to the blob URL on download.
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('種類・サイズ・位置・色を半角 " - " で連結する（Tシャツ）', async () => {
    const csv = await exportCsvText()
    expect(csv).toContain('Tシャツ - M - 正面 - 白')
  })

  it('値が無い要素（位置なし）をスキップし余分な区切りを出さない（ステッカー）', async () => {
    const csv = await exportCsvText()
    expect(csv).toContain('ステッカー - 100x100mm - ホワイト')
  })

  it('acrylic_stand は「アクリルフィギュア」にマッピングされる', async () => {
    const csv = await exportCsvText()
    expect(csv).toContain('アクリルフィギュア - 100mm - クリア')
    expect(csv).not.toContain('アクリルスタンド')
  })

  it('サイズ・位置・色が無い場合は商品種類名のみを出力する（アクリルキーホルダー）', async () => {
    const csv = await exportCsvText()
    // CSVセルは引用符で囲まれるため、完全一致セルとして検証（末尾に余分な区切りが付かない）
    expect(csv).toContain('"アクリルキーホルダー"')
  })
})
