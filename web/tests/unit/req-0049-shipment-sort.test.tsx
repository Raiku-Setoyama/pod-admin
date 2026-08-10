/**
 * REQ-0049: 配送一覧を作成日・配送予定日・ステータス・注文番号・宛先で
 * 昇順／降順に並び替えられる。
 *
 * - 5 列の見出しから並び替えを操作できる
 * - 選択中の列と向き（昇順／降順）が画面上で判別できる
 * - 別の列は昇順から始まり、選択中の列は向きが入れ替わる
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

import { ShipmentList } from '@/features/shipments/components/shipment-list'
import type { Shipment, ShipmentSortBy, ShipmentSortOrder, ShipmentStatus } from '@/types/api'

const SORTABLE_COLUMNS: { label: string; column: ShipmentSortBy }[] = [
  { label: '注文番号', column: 'order_number' },
  { label: '宛先', column: 'customer_name' },
  { label: '作成日', column: 'created_at' },
  { label: '配送予定日', column: 'estimated_shipping_date' },
  { label: 'ステータス', column: 'status' },
]

const mockShipment: Shipment = {
  id: 'shipment-0049',
  status: 'pending' as ShipmentStatus,
  tracking_number: 'TRK-0049',
  carrier: null,
  packing_photo_path: null,
  shipped_at: null,
  delivered_at: null,
  note: null,
  customer_name: 'テスト宛先',
  customer_postal_code: '100-0001',
  customer_address_prefecture: '東京都',
  customer_address_city: '千代田区',
  customer_address_building: null,
  customer_full_address: '東京都千代田区',
  customer_phone: '090-1234-5678',
  estimated_shipping_date: null,
  items: [
    {
      id: 'item-1',
      order_id: 'order-1',
      order_number: 'ORD-0049',
      product_name: '商品A',
      quantity: 1,
      thumbnail_image_url: null,
    },
  ],
  created_at: '2026-08-08T09:00:00Z',
  updated_at: '2026-08-08T09:00:00Z',
}

function renderList(
  overrides: {
    sortBy?: ShipmentSortBy
    sortOrder?: ShipmentSortOrder
    onSortChange?: (sortBy: ShipmentSortBy, sortOrder: ShipmentSortOrder) => void
  } = {}
) {
  const onSortChange = overrides.onSortChange ?? vi.fn()
  render(
    <ShipmentList
      shipments={[mockShipment]}
      selectedIds={new Set()}
      onSelectChange={vi.fn()}
      sortBy={overrides.sortBy ?? 'created_at'}
      sortOrder={overrides.sortOrder ?? 'desc'}
      onSortChange={onSortChange}
    />
  )
  return { onSortChange }
}

describe('REQ-0049: 配送一覧の並び替え', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('並び替え対象の 5 列がすべて操作できる', () => {
    renderList()

    for (const { label } of SORTABLE_COLUMNS) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
  })

  it('並び替えの対象でない列は操作対象にならない', () => {
    renderList()

    for (const label of ['配送ID', '商品数', '伝票番号']) {
      expect(screen.queryByRole('button', { name: label })).not.toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: label })).toBeInTheDocument()
    }
  })

  it('既定（作成日の降順）では作成日だけが降順として示される', () => {
    renderList()

    expect(screen.getByRole('columnheader', { name: '作成日' })).toHaveAttribute(
      'aria-sort',
      'descending'
    )
    for (const { label } of SORTABLE_COLUMNS.filter((c) => c.label !== '作成日')) {
      expect(screen.getByRole('columnheader', { name: label })).toHaveAttribute('aria-sort', 'none')
    }
  })

  it('選択中の列は昇順・降順が画面上で判別できる', () => {
    renderList({ sortBy: 'status', sortOrder: 'asc' })

    expect(screen.getByRole('columnheader', { name: 'ステータス' })).toHaveAttribute(
      'aria-sort',
      'ascending'
    )
  })

  it('選択されていない列を押すと昇順で並び替える', async () => {
    const user = userEvent.setup()
    const { onSortChange } = renderList()

    await user.click(screen.getByRole('button', { name: '注文番号' }))

    expect(onSortChange).toHaveBeenCalledWith('order_number', 'asc')
  })

  it('選択中の列を押すと向きが入れ替わる', async () => {
    const user = userEvent.setup()
    const { onSortChange } = renderList({ sortBy: 'customer_name', sortOrder: 'asc' })

    await user.click(screen.getByRole('button', { name: '宛先' }))

    expect(onSortChange).toHaveBeenCalledWith('customer_name', 'desc')
  })

  it('並び替えを渡さない使い方では、従来どおりの列見出しのままになる', () => {
    render(
      <ShipmentList shipments={[mockShipment]} selectedIds={new Set()} onSelectChange={vi.fn()} />
    )

    expect(screen.queryByRole('button', { name: '作成日' })).not.toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '作成日' })).toBeInTheDocument()
  })
})
