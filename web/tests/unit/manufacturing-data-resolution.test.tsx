/**
 * 製造データ一覧・詳細の元画像の解像度と印刷の条件（DTF。#190）
 *
 * 区分（resolution_level）は API が設定の閾値で判定して返す。画面は閾値を持たず、
 * low＝「低解像度」、upscaled＝「拡大して作成」、ok＝区分なし、記録なし＝「—」と出す。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { SWRConfig } from 'swr'
import { ManufacturingDataDetailSheet } from '@/features/manufacturing-data/components/manufacturing-data-detail-sheet'
import { ManufacturingDataList } from '@/features/manufacturing-data/components/manufacturing-data-list'
import { formatDpi, formatTopBelowRib } from '@/features/manufacturing-data/components/print-record'
import { apiClient } from '@/lib/api/client'
import type { ManufacturingDataDetail, ManufacturingDataRow } from '@/types/api'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  downloadFile: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const mockedApiClient = vi.mocked(apiClient)

beforeEach(() => {
  vi.clearAllMocks()
})

function row(overrides: Partial<ManufacturingDataRow> = {}): ManufacturingDataRow {
  return {
    id: 'md-1',
    status: 'ready',
    output_filename: 'RKSYO-T_XL.pdf',
    file_size: 1024,
    error_message: null,
    order_source_id: null,
    product_code: 'RKSYO-T',
    product_type: 'tshirt',
    size: 'XL',
    variant: 'dtf',
    vm_job_id: null,
    attempts: 1,
    source_images_replaced_by: null,
    created_at: '2026-11-13T00:00:00Z',
    updated_at: '2026-11-13T00:00:00Z',
    source_dpi: 101.7,
    resolution_level: 'low',
    art_width_mm: 295,
    art_height_mm: 295,
    art_top_below_rib_mm: 136,
    white_plate: 'mixed',
    ...overrides,
  }
}

function resolutionCell(code: string): HTMLElement {
  const tr = screen.getByText(code).closest('tr') as HTMLElement
  // 列の並び: ステータス / 商品コード / 商品種別 / サイズ・バリアント / 解像度
  return within(tr).getAllByRole('cell')[4]
}

describe('formatDpi', () => {
  it('区分と食い違わないよう小数 1 桁で切り捨てる', () => {
    expect(formatDpi(101.7)).toBe('101.7 dpi')
    expect(formatDpi(149.96)).toBe('149.9 dpi')
    expect(formatDpi(150)).toBe('150 dpi')
    expect(formatDpi(300)).toBe('300 dpi')
  })
})

describe('formatTopBelowRib', () => {
  it('発注リストと同じく 0.1cm 単位に四捨五入する', () => {
    expect(formatTopBelowRib(135.5)).toBe('13.6 cm')
    expect(formatTopBelowRib(135.45)).toBe('13.5 cm')
    expect(formatTopBelowRib(136)).toBe('13.6 cm')
    expect(formatTopBelowRib(41)).toBe('4.1 cm')
  })
})

describe('ManufacturingDataList の解像度列', () => {
  it('境界値: 149.9＝低解像度、150＝拡大して作成、300＝区分なし、記録なし＝「—」', () => {
    render(
      <ManufacturingDataList
        items={[
          row({ id: 'a', product_code: 'LOW', source_dpi: 149.9, resolution_level: 'low' }),
          row({ id: 'b', product_code: 'UP', source_dpi: 150, resolution_level: 'upscaled' }),
          row({ id: 'c', product_code: 'OK', source_dpi: 300, resolution_level: 'ok' }),
          row({
            id: 'd',
            product_code: 'NONE',
            product_type: 'acrylic_keychain',
            variant: 'clear',
            source_dpi: null,
            resolution_level: null,
            art_width_mm: null,
            art_height_mm: null,
            art_top_below_rib_mm: null,
            white_plate: null,
          }),
        ]}
      />,
    )

    expect(screen.getByRole('columnheader', { name: '解像度' })).toBeInTheDocument()

    const low = resolutionCell('LOW')
    expect(low).toHaveTextContent('149.9 dpi')
    expect(within(low).getByText('低解像度')).toBeInTheDocument()

    const up = resolutionCell('UP')
    expect(up).toHaveTextContent('150 dpi')
    expect(within(up).getByText('拡大して作成')).toBeInTheDocument()

    const ok = resolutionCell('OK')
    expect(ok).toHaveTextContent('300 dpi')
    expect(within(ok).queryByText('低解像度')).not.toBeInTheDocument()
    expect(within(ok).queryByText('拡大して作成')).not.toBeInTheDocument()

    expect(resolutionCell('NONE')).toHaveTextContent(/^—$/)
  })

  it('生成待ちの行は前回の値が残っていても出さない', () => {
    render(<ManufacturingDataList items={[row({ product_code: 'PEND', status: 'pending' })]} />)

    const cell = resolutionCell('PEND')
    expect(cell).toHaveTextContent(/^—$/)
    expect(within(cell).queryByText('低解像度')).not.toBeInTheDocument()
  })
})

function detail(overrides: Partial<ManufacturingDataDetail> = {}): ManufacturingDataDetail {
  // 一覧の行と同じ値に、詳細だけの項目を足す
  return {
    ...row(),
    source_images_replaced_at: null,
    source_images: [],
    order_items: [],
    order_items_total: 0,
    ...overrides,
  }
}

function renderSheet(data: ManufacturingDataDetail) {
  mockedApiClient.mockResolvedValue(data)
  render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ManufacturingDataDetailSheet manufacturingDataId={data.id} onClose={vi.fn()} />
    </SWRConfig>,
  )
}

describe('ManufacturingDataDetailSheet の印刷の条件（DTF）', () => {
  it('解像度・絵柄の大きさ・リブ下からの位置・白版の種類を出す', async () => {
    renderSheet(detail())

    const section = (await screen.findByText('印刷の条件（DTF）')).closest('section') as HTMLElement
    expect(within(section).getByText('101.7 dpi')).toBeInTheDocument()
    expect(within(section).getByText('低解像度')).toBeInTheDocument()
    expect(within(section).getByText(/仕上がりが粗くなる場合があります/)).toBeInTheDocument()
    expect(within(section).getByText('295 × 295 mm')).toBeInTheDocument()
    expect(within(section).getByText('13.6 cm')).toBeInTheDocument()
    expect(within(section).getByText('混在（カラー部分を縮小済み）')).toBeInTheDocument()
  })

  it('拡大して作成のときは、拡大した旨を出す', async () => {
    renderSheet(detail({ source_dpi: 200, resolution_level: 'upscaled', white_plate: 'color_only' }))

    const section = (await screen.findByText('印刷の条件（DTF）')).closest('section') as HTMLElement
    expect(within(section).getByText('拡大して作成')).toBeInTheDocument()
    expect(within(section).getByText(/システムが拡大して作成しました/)).toBeInTheDocument()
    expect(within(section).getByText('カラーのみ（縮小なし）')).toBeInTheDocument()
  })

  it('目標以上なら区分も説明も出さない', async () => {
    renderSheet(detail({ source_dpi: 300, resolution_level: 'ok' }))

    const section = (await screen.findByText('印刷の条件（DTF）')).closest('section') as HTMLElement
    expect(within(section).getByText('300 dpi')).toBeInTheDocument()
    expect(within(section).queryByText('低解像度')).not.toBeInTheDocument()
    expect(within(section).queryByText('拡大して作成')).not.toBeInTheDocument()
  })

  it('生成が終わっていなければ値を出さない（前回の値が残っているため）', async () => {
    renderSheet(detail({ status: 'pending' }))

    const section = (await screen.findByText('印刷の条件（DTF）')).closest('section') as HTMLElement
    expect(within(section).getByText('生成が終わると表示されます')).toBeInTheDocument()
    expect(within(section).queryByText('101.7 dpi')).not.toBeInTheDocument()
  })

  it('DTF 版でなければ印刷の条件の欄は出さない', async () => {
    renderSheet(
      detail({
        product_type: 'acrylic_keychain',
        variant: 'clear',
        source_dpi: null,
        resolution_level: null,
        art_width_mm: null,
        art_height_mm: null,
        art_top_below_rib_mm: null,
        white_plate: null,
      }),
    )

    expect(await screen.findByText('製造データの詳細')).toBeInTheDocument()
    await screen.findByText('使っている注文（0 件）')
    expect(screen.queryByText('印刷の条件（DTF）')).not.toBeInTheDocument()
  })
})
