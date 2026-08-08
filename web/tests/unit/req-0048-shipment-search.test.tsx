/**
 * REQ-0048: 配送一覧の検索欄の表記が、実際の検索対象と一致する。
 *
 * - 検索欄のプレースホルダが「配送ID、伝票番号、注文番号、宛先名で検索...」になっている
 * - 配送一覧の画面から「顧客名」という表記がなくなっている
 *   （同じ値を検索欄では「顧客名」、一覧では「宛先」と呼び分けていたのをやめる）
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn() },
}))

import { ShipmentFilters } from '@/features/shipments/components/shipment-filters'
import { ShipmentList } from '@/features/shipments/components/shipment-list'
import type { Shipment, ShipmentStatus } from '@/types/api'

const SEARCH_PLACEHOLDER = '配送ID、伝票番号、注文番号、宛先名で検索...'

function createFilterProps() {
  return {
    search: '',
    status: null,
    onSearchChange: vi.fn(),
    onStatusChange: vi.fn(),
    onReset: vi.fn(),
  }
}

const mockShipment: Shipment = {
  id: 'shipment-0048',
  status: 'pending' as ShipmentStatus,
  tracking_number: 'TRK-0048',
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
      order_number: 'ORD-0048',
      product_name: '商品A',
      quantity: 1,
      thumbnail_image_url: null,
    },
  ],
  created_at: '2026-08-08T09:00:00Z',
  updated_at: '2026-08-08T09:00:00Z',
}

describe('REQ-0048: 検索欄の表記が実際の検索対象と一致する', () => {
  it('検索欄のプレースホルダに検索対象がそのまま並んでいる', () => {
    render(<ShipmentFilters {...createFilterProps()} />)

    expect(screen.getByPlaceholderText(SEARCH_PLACEHOLDER)).toBeInTheDocument()
  })

  it('検索欄に「顧客名」という表記が残っていない', () => {
    const { container } = render(<ShipmentFilters {...createFilterProps()} />)

    expect(container.textContent).not.toContain('顧客名')
    expect(screen.queryByPlaceholderText(/顧客名/)).not.toBeInTheDocument()
  })

  it('一覧の列見出しに「顧客名」がなく「宛先」で統一されている', () => {
    const { container } = render(
      <ShipmentList
        shipments={[mockShipment]}
        selectedIds={new Set()}
        onSelectChange={vi.fn()}
      />
    )

    expect(container.textContent).not.toContain('顧客名')
    expect(screen.getByRole('columnheader', { name: '宛先' })).toBeInTheDocument()
  })
})
