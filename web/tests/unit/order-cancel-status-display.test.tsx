/**
 * 注文キャンセルの明細ステータス表示テスト
 *
 * 注文が cancelled になった明細が、メーカー画面（管理側の発注詳細・全メーカー一覧）と
 * メーカーポータル（manufacturer-login）で「発注済み」ではなく「キャンセル済み」として
 * 表示されることを検証する。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

import { StatusBadge } from '@/components/common/status-badge'
import { ManufacturerOrderDetail } from '@/features/purchase-orders/components/manufacturer-order-detail'
import { AllManufacturerOrderList } from '@/features/purchase-orders/components/all-manufacturer-order-list'
import {
  ORDER_STATUS_LABELS,
  getManufacturerOrderFilterStatusOptions,
} from '@/constants/status'
import type {
  AllManufacturerOrderItemListResponse,
  ManufacturerOrderItemListResponse,
  OrderStatus,
} from '@/types/api'

const CANCELLED_LABEL = 'キャンセル済み'
const PRODUCT_NAME = 'キャンセルされたTシャツ'

/** キャンセル済み明細1件（メーカー画面・ポータル共通の形） */
const cancelledItem = {
  id: 'item-001',
  order_id: 'order-001',
  order_number: 'ORD-001',
  uid: '0000001',
  product_id: 'prod-001',
  product_name: PRODUCT_NAME,
  product_type: 'tshirt',
  price: 1000,
  quantity: 1,
  size: 'M',
  position: '正面',
  color: '白',
  design_image_url: null,
  thumbnail_image_url: null,
  ordered_at: '2026-07-20T10:00:00Z',
  customer_name: '田中太郎',
  status: 'cancelled',
  lead_time_days: 10,
  expected_delivery_date: '2026-07-30',
} as const

const totals = { total: 1, total_quantity: 1, total_amount: 1000 }

function createCancelledItemsData(): ManufacturerOrderItemListResponse {
  return {
    manufacturer_id: 'mfr-001',
    manufacturer_name: 'テストメーカー',
    items: [{ ...cancelledItem }],
    ...totals,
  }
}

function createCancelledAllItemsData(): AllManufacturerOrderItemListResponse {
  return {
    items: [
      { ...cancelledItem, manufacturer_id: 'mfr-001', manufacturer_name: 'テストメーカー' },
    ],
    ...totals,
  }
}

function createDetailProps() {
  return {
    data: createCancelledItemsData(),
    isLoading: false,
    onStatusUpdate: vi.fn(),
    search: '',
    status: null as OrderStatus | null,
    onSearchChange: vi.fn(),
    onStatusChange: vi.fn(),
    onFilterReset: vi.fn(),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('cancelled ステータスのラベル', () => {
  it('OrderStatus のラベルに cancelled が定義されている', () => {
    expect(ORDER_STATUS_LABELS.cancelled).toBe(CANCELLED_LABEL)
  })

  it('StatusBadge が cancelled を「キャンセル済み」として表示する（生の値を出さない）', () => {
    render(<StatusBadge status="cancelled" />)

    expect(screen.getByText(CANCELLED_LABEL)).toBeInTheDocument()
    expect(screen.queryByText('cancelled')).not.toBeInTheDocument()
  })
})

describe('メーカー画面（管理側）でキャンセル済みが表示される', () => {
  it('発注詳細の明細行が「キャンセル済み」バッジを表示する', () => {
    render(<ManufacturerOrderDetail {...createDetailProps()} />)

    const row = screen.getByText(PRODUCT_NAME).closest('tr')
    expect(within(row!).getByText(CANCELLED_LABEL)).toBeInTheDocument()
    expect(within(row!).queryByText('発注済み')).not.toBeInTheDocument()
  })

  it('全メーカー横断一覧の明細行が「キャンセル済み」バッジを表示する', () => {
    render(
      <AllManufacturerOrderList data={createCancelledAllItemsData()} isLoading={false} />
    )

    const row = screen.getByText(PRODUCT_NAME).closest('tr')
    expect(within(row!).getByText(CANCELLED_LABEL)).toBeInTheDocument()
  })

  it('キャンセル済みの明細は発注対象として選択できない', () => {
    render(<ManufacturerOrderDetail {...createDetailProps()} />)

    const row = screen.getByText(PRODUCT_NAME).closest('tr')
    expect(within(row!).getByRole('checkbox')).toBeDisabled()
  })

  it('ステータスフィルターに「キャンセル済み」の選択肢がある', () => {
    expect(getManufacturerOrderFilterStatusOptions()).toContainEqual({
      value: 'cancelled',
      label: CANCELLED_LABEL,
    })
  })
})

describe('メーカーポータル（manufacturer-login）でキャンセル済みが表示される', () => {
  it('明細一覧が「キャンセル済み」バッジを表示する', async () => {
    vi.doMock('@/features/manufacturer-portal/hooks/use-manufacturer-orders', () => ({
      useManufacturerOrderItems: () => ({
        items: createCancelledItemsData().items,
        total: 1,
        totalQuantity: 1,
        isLoading: false,
        isFiltering: false,
      }),
      downloadAllOrderDocuments: vi.fn(),
    }))

    const { default: ManufacturerDashboardPage } = await import(
      '@/app/(manufacturer)/manufacturer/page'
    )

    render(<ManufacturerDashboardPage />)

    const row = screen.getByText(PRODUCT_NAME).closest('tr')
    expect(within(row!).getByText(CANCELLED_LABEL)).toBeInTheDocument()
    expect(within(row!).queryByText('発注済み')).not.toBeInTheDocument()
  })
})
