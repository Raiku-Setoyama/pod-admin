/**
 * 製造データ詳細パネルのテスト
 *
 * 一覧の行をクリックすると、その製造データの詳細（エラー全文・生成済みファイル・
 * 元画像・使っている注文）が右側のパネルで見られることを検証する。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SWRConfig } from 'swr'
import type { ReactNode } from 'react'
import { ManufacturingDataDetailSheet } from '@/features/manufacturing-data/components/manufacturing-data-detail-sheet'
import { ManufacturingDataList } from '@/features/manufacturing-data/components/manufacturing-data-list'
import { apiClient, downloadFile } from '@/lib/api/client'
import type { ManufacturingDataDetail, ManufacturingDataRow } from '@/types/api'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  downloadFile: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const mockedApiClient = vi.mocked(apiClient)
const mockedDownloadFile = vi.mocked(downloadFile)

function withSWR(ui: ReactNode) {
  return (
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>{ui}</SWRConfig>
  )
}

function detail(overrides: Partial<ManufacturingDataDetail> = {}): ManufacturingDataDetail {
  return {
    id: 'md-1',
    product_code: 'RKSYO-ABC',
    product_type: 'acrylic_keychain',
    size: '50x50mm',
    variant: 'clear',
    status: 'ready',
    output_filename: 'RKSYO-ABC_50x50.ai',
    file_size: 2048,
    error_message: null,
    attempts: 1,
    created_at: '2026-11-10T01:00:00Z',
    updated_at: '2026-11-10T01:05:00Z',
    source_images: [
      { layer_type: 'color', origin: 'external', url: 'https://example.com/color.png', filename: null },
      { layer_type: 'cutline', origin: 'uploaded', url: null, filename: 'cutline_fix.png' },
    ],
    source_images_replaced_at: null,
    source_images_replaced_by: null,
    order_items: [
      {
        order_id: 'order-1',
        order_number: '1000001',
        order_status: 'ordered',
        ordered_at: '2026-11-10T00:00:00Z',
        item_id: 'item-1',
        item_status: 'ordered',
        product_name: 'アクリルキーホルダー A',
        quantity: 2,
      },
    ],
    order_items_total: 1,
    source_dpi: null,
    resolution_level: null,
    art_width_mm: null,
    art_height_mm: null,
    art_top_below_rib_mm: null,
    white_plate: null,
    ...overrides,
  }
}

function renderSheet(data: ManufacturingDataDetail, onClose = vi.fn()) {
  mockedApiClient.mockResolvedValue(data)
  render(withSWR(<ManufacturingDataDetailSheet manufacturingDataId={data.id} onClose={onClose} />))
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('ManufacturingDataDetailSheet', () => {
  it('詳細を取得して、基本情報と使っている注文を表示する', async () => {
    renderSheet(detail())

    expect(await screen.findByText('製造データの詳細')).toBeInTheDocument()
    expect(mockedApiClient).toHaveBeenCalledWith('/manufacturing-data/md-1')
    expect(await screen.findByText('RKSYO-ABC_50x50.ai')).toBeInTheDocument()

    const orderLink = screen.getByRole('link', { name: '1000001' })
    expect(orderLink).toHaveAttribute('href', '/orders/order-1')
    expect(screen.getByText('使っている注文（1 件）')).toBeInTheDocument()
  })

  it('エラー文は一覧で切らずに全文を出す', async () => {
    const message = 'source image fetch failed: '.repeat(10)
    renderSheet(detail({ status: 'failed', error_message: message }))

    const pre = await screen.findByText((_, el) => el?.tagName === 'PRE')
    expect(pre.textContent).toBe(message)
  })

  it('生成済みなら .ai をダウンロードできる', async () => {
    const user = userEvent.setup()
    renderSheet(detail())

    const fileRow = (await screen.findByText('RKSYO-ABC_50x50.ai')).closest('div.flex')
    const button = fileRow?.querySelector('button')
    expect(button).toBeTruthy()
    await user.click(button as HTMLButtonElement)

    expect(mockedDownloadFile).toHaveBeenCalledWith(
      '/manufacturing-data/md-1/file',
      'RKSYO-ABC_50x50.ai',
    )
  })

  it('生成が終わっていなければ .ai のダウンロードボタンは出さない', async () => {
    renderSheet(detail({ status: 'pending', output_filename: null, file_size: null }))

    expect(await screen.findByText(/生成が終わるとダウンロードできます/)).toBeInTheDocument()
  })

  it('見出しの拡張子は製造データのファイルに合わせる（アクリル系は .ai）', async () => {
    renderSheet(detail())

    expect(
      await screen.findByRole('heading', { name: '製造データ（.ai）' }),
    ).toBeInTheDocument()
  })

  it('T シャツ・トートの PDF は見出しが .pdf になり、PDF のファイル名でダウンロードする', async () => {
    const user = userEvent.setup()
    renderSheet(
      detail({
        product_code: 'RKSYO-TEE',
        product_type: 'tshirt',
        size: 'M',
        variant: 'dtf',
        output_filename: 'Tシャツ_M_md-1.pdf',
      }),
    )

    const heading = await screen.findByRole('heading', { name: '製造データ（.pdf）' })
    expect(screen.queryByRole('heading', { name: '製造データ（.ai）' })).not.toBeInTheDocument()

    const section = within(heading.closest('section') as HTMLElement)
    expect(section.getByText('Tシャツ_M_md-1.pdf')).toBeInTheDocument()
    await user.click(section.getByRole('button', { name: 'ダウンロード' }))
    expect(mockedDownloadFile).toHaveBeenCalledWith(
      '/manufacturing-data/md-1/file',
      'Tシャツ_M_md-1.pdf',
    )
  })

  it.each([
    ['pending', null],
    ['generating', null],
    ['failed', null],
    // 再生成で生成待ちに戻った行は前回のファイル名が残るが、まだダウンロードできない
    ['pending', 'RKSYO-ABC_50x50.ai'],
  ] as const)(
    'ファイルがまだ無い（%s・ファイル名 %s）ときは見出しに拡張子を付けない',
    async (status, outputFilename) => {
      renderSheet(detail({ status, output_filename: outputFilename, file_size: null }))

      expect(await screen.findByRole('heading', { name: '製造データ' })).toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: /製造データ（/ })).not.toBeInTheDocument()
    },
  )

  it('生成済みでもファイル名が分からなければ、拡張子を推測で付けない', async () => {
    const user = userEvent.setup()
    renderSheet(detail({ output_filename: null }))

    const heading = await screen.findByRole('heading', { name: '製造データ' })
    const section = within(heading.closest('section') as HTMLElement)
    expect(section.getByText('RKSYO-ABC')).toBeInTheDocument()
    await user.click(section.getByRole('button', { name: 'ダウンロード' }))
    expect(mockedDownloadFile).toHaveBeenCalledWith('/manufacturing-data/md-1/file', 'RKSYO-ABC')
  })

  it('差し替え済みの元画像はダウンロードでき、外部の元画像はリンクで開く', async () => {
    const user = userEvent.setup()
    renderSheet(detail())

    expect(await screen.findByRole('link', { name: '開く' })).toHaveAttribute(
      'href',
      'https://example.com/color.png',
    )
    const cutlineRow = screen.getByText('差し替え済み: cutline_fix.png').closest('li')
    await user.click(cutlineRow?.querySelector('button') as HTMLButtonElement)
    expect(mockedDownloadFile).toHaveBeenCalledWith(
      '/manufacturing-data/md-1/source-images/cutline',
      'cutline_fix.png',
    )
  })

  it('http(s) 以外の外部 URL はリンクにしない（javascript: などを踏ませない）', async () => {
    renderSheet(
      detail({
        source_images: [
          { layer_type: 'color', origin: 'external', url: 'javascript:alert(1)', filename: null },
        ],
      }),
    )

    expect(await screen.findByText('外部受注の元画像')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '開く' })).not.toBeInTheDocument()
  })

  it('使っている注文が上限より多いときは残りの件数を出す', async () => {
    renderSheet(detail({ order_items_total: 51 }))

    expect(await screen.findByText(/ほか 50 件/)).toBeInTheDocument()
  })
})

describe('ManufacturingDataList の行クリック', () => {
  const rows: ManufacturingDataRow[] = [
    {
      id: 'md-9',
      status: 'failed',
      output_filename: null,
      file_size: null,
      error_message: 'boom',
      order_source_id: null,
      product_code: 'RKSYO-FAIL',
      product_type: 'acrylic_keychain',
      size: null,
      variant: null,
      vm_job_id: null,
      attempts: 3,
      source_images_replaced_by: null,
      created_at: '2026-11-10T00:00:00Z',
      updated_at: '2026-11-10T00:00:00Z',
      source_dpi: null,
      resolution_level: null,
      art_width_mm: null,
      art_height_mm: null,
      art_top_below_rib_mm: null,
      white_plate: null,
    },
  ]

  it('行をクリックすると詳細を開く', async () => {
    const user = userEvent.setup()
    const onRowClick = vi.fn()
    render(<ManufacturingDataList items={rows} onRowClick={onRowClick} />)

    await user.click(screen.getByText('RKSYO-FAIL'))
    expect(onRowClick).toHaveBeenCalledWith('md-9')
  })

  it('チェックボックスの操作では詳細を開かない', async () => {
    const user = userEvent.setup()
    const onRowClick = vi.fn()
    const onSelectChange = vi.fn()
    render(
      <ManufacturingDataList
        items={rows}
        selectedIds={[]}
        onSelectChange={onSelectChange}
        onRowClick={onRowClick}
      />,
    )

    await user.click(screen.getByRole('checkbox', { name: 'RKSYO-FAIL を選択' }))
    expect(onSelectChange).toHaveBeenCalledWith(['md-9'])
    expect(onRowClick).not.toHaveBeenCalled()
  })
})
