/**
 * データ出力タブ（REQ-0047 / Issue #172）の単体テスト。
 *
 * - 項目は分類ごとに折りたたまれ、検索で絞れる。チェックした項目だけがリクエストの列になる
 * - 項目が 0 個なら出力できない
 * - 選んだ項目でプレビュー（先頭の行と総件数）を出す
 * - 絞り込みはプレビュー上の条件チップ、並べ替えは見出しのクリックでもできる
 * - 絞り込み・並べ替えがリクエストに入る
 * - サイドバーに「データ出力」がある
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  downloadFileByPost: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/features/auth/hooks/use-current-user', () => ({
  useCurrentUser: vi.fn(() => ({ user: undefined, isLoading: true, error: undefined, mutate: vi.fn() })),
}))

vi.mock('next/navigation', () => ({
  usePathname: () => '/data-export',
}))

import { SWRConfig } from 'swr'
import { apiClient, downloadFileByPost } from '@/lib/api/client'
import { toast } from 'sonner'
import { DataExportForm } from '@/features/data-export/components/data-export-form'
import {
  buildDataExportRequest,
  dataExportFilename,
  groupDataExportColumns,
} from '@/features/data-export/utils/build-data-export-request'
import { Sidebar } from '@/components/layout/sidebar'
import type { DataExportColumn } from '@/types/api'

const mockDownload = vi.mocked(downloadFileByPost)
const mockApiClient = vi.mocked(apiClient)

const columns: DataExportColumn[] = [
  { key: 'order_number', label: '注文番号', group: '受注' },
  { key: 'ordered_at', label: '受注日時', group: '受注' },
  { key: 'customer_name', label: 'お客様氏名', group: '顧客（お届け先）' },
  { key: 'customer_phone', label: 'お届け先電話番号', group: '顧客（お届け先）' },
  { key: 'item_quantity', label: '数量', group: '受注明細' },
]

const emptyState = {
  selectedKeys: new Set<string>(),
  search: '',
  status: null,
  productType: null,
  orderedRange: undefined,
  shippingRange: undefined,
  sortColumn: null,
  sortDirection: 'asc' as const,
}

describe('buildDataExportRequest', () => {
  it('列は項目一覧の順で、チェックした項目だけになる', () => {
    const request = buildDataExportRequest(columns, {
      ...emptyState,
      selectedKeys: new Set(['item_quantity', 'order_number']),
    })
    expect(request.columns).toEqual(['order_number', 'item_quantity'])
    expect(request.sort).toBeNull()
  })

  it('絞り込みと並べ替えを API の形にする', () => {
    const request = buildDataExportRequest(columns, {
      ...emptyState,
      selectedKeys: new Set(['order_number']),
      search: '  山田 ',
      status: 'ordered',
      productType: 'sticker',
      orderedRange: { from: new Date(2026, 10, 1), to: new Date(2026, 10, 30) },
      shippingRange: { from: new Date(2026, 11, 1), to: undefined },
      sortColumn: 'item_quantity',
      sortDirection: 'desc',
    })
    expect(request.filters).toEqual({
      status: 'ordered',
      product_type: 'sticker',
      ordered_from: '2026-11-01',
      ordered_to: '2026-11-30',
      shipping_from: '2026-12-01',
      shipping_to: null,
      search: '山田',
    })
    expect(request.sort).toEqual({ column: 'item_quantity', direction: 'desc' })
  })

  it('空のキーワードは送らない', () => {
    const request = buildDataExportRequest(columns, { ...emptyState, search: '   ' })
    expect(request.filters.search).toBeNull()
  })

  it('分類ごとにまとめる（順序は保つ）', () => {
    expect(groupDataExportColumns(columns).map((g) => [g.group, g.columns.length])).toEqual([
      ['受注', 2],
      ['顧客（お届け先）', 2],
      ['受注明細', 1],
    ])
  })

  it('ファイル名は データ出力_yyyyMMdd_HHmmss.csv', () => {
    expect(dataExportFilename(new Date(2026, 10, 12, 9, 5, 7))).toBe('データ出力_20261112_090507.csv')
  })
})

function renderForm() {
  // テストごとに SWR のキャッシュを分ける
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <DataExportForm columns={columns} />
    </SWRConfig>
  )
}

const previewResponse = {
  headers: ['注文番号', '数量'],
  rows: [
    ['A-001', '2'],
    ['A-002', ''],
  ],
  total_count: 37,
  unfiltered_count: 120,
}

/** 最後に投げたプレビューのリクエスト本文 */
function lastPreviewBody() {
  const [endpoint, options] = mockApiClient.mock.calls.at(-1)!
  expect(endpoint).toBe('/data-export/preview')
  return (options as { body: Record<string, unknown> }).body
}

describe('DataExportForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApiClient.mockResolvedValue(previewResponse)
  })

  it('分類は最初は閉じていて、開くと項目が出る', async () => {
    const user = userEvent.setup()
    renderForm()
    expect(screen.getByRole('button', { name: /顧客（お届け先）/ })).toHaveAttribute(
      'aria-expanded',
      'false'
    )
    expect(screen.queryByLabelText('お客様氏名')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /顧客（お届け先）/ }))
    expect(screen.getByLabelText('お客様氏名')).toBeInTheDocument()
  })

  it('項目名で探すと、当てはまる項目だけが分類を開いた状態で出る', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(screen.getByLabelText('項目を検索'), '電話')
    expect(screen.getByLabelText('お届け先電話番号')).toBeInTheDocument()
    expect(screen.queryByLabelText('お客様氏名')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('受注明細の当てはまる項目をすべて選択')).not.toBeInTheDocument()

    await user.clear(screen.getByLabelText('項目を検索'))
    await user.type(screen.getByLabelText('項目を検索'), '存在しない')
    expect(screen.getByText('「存在しない」に当てはまる項目はありません')).toBeInTheDocument()
  })

  it('項目が 0 個のときは出力できず、プレビューも取りに行かない', () => {
    renderForm()
    expect(screen.getByRole('button', { name: /CSV を出力/ })).toBeDisabled()
        expect(mockApiClient).not.toHaveBeenCalled()
  })

  it('チェックした項目だけを列にして出力する（個人情報は選ばなければ出ない）', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.type(screen.getByLabelText('項目を検索'), '注文番号')
    await user.click(screen.getByLabelText('注文番号'))
    await user.clear(screen.getByLabelText('項目を検索'))
    await user.type(screen.getByLabelText('項目を検索'), '数量')
    await user.click(screen.getByLabelText('数量'))
    await user.click(screen.getByRole('button', { name: /CSV を出力/ }))

    expect(mockDownload).toHaveBeenCalledTimes(1)
    const [endpoint, body, filename] = mockDownload.mock.calls[0]
    expect(endpoint).toBe('/data-export/csv')
    expect(body).toMatchObject({ columns: ['order_number', 'item_quantity'] })
    expect(filename).toMatch(/^データ出力_\d{8}_\d{6}\.csv$/)
  })

  it('選んだ数が項目一覧の見出しに出る', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByLabelText('受注をすべて選択'))
    expect(screen.getByText('2 / 5')).toBeInTheDocument()
  })

  it('分類のチェックでその分類の項目をまとめて選ぶ・外す', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByRole('button', { name: /顧客（お届け先）/ }))

    const group = screen.getByLabelText('顧客（お届け先）をすべて選択')
    await user.click(group)
    expect(screen.getByLabelText('お客様氏名')).toBeChecked()
    expect(screen.getByLabelText('お届け先電話番号')).toBeChecked()

    await user.click(group)
    expect(screen.getByLabelText('お客様氏名')).not.toBeChecked()
  })

  it('すべて選択・すべて解除', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByRole('button', { name: 'すべて選択' }))
    expect(screen.getByText('5 / 5')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'すべて解除' }))
    expect(screen.getByText('0 / 5')).toBeInTheDocument()
  })

  it('項目を選ぶとプレビューを取りに行き、先頭の行と総件数を出す', async () => {
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByLabelText('受注明細をすべて選択'))

    expect(await screen.findByText('A-001')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '注文番号' })).toBeInTheDocument()
    expect(screen.getByText('37 件')).toBeInTheDocument()
    // 絞り込みがないときは「全 N 件」
    expect(screen.queryByText(/120 件中/)).not.toBeInTheDocument()
    expect(screen.getByText(/先頭 2 件を表示/)).toBeInTheDocument()

    const [endpoint, options] = mockApiClient.mock.calls.at(-1)!
    expect(endpoint).toBe('/data-export/preview')
    expect(options).toMatchObject({ method: 'POST', body: { columns: ['item_quantity'] } })
  })

  it('当てはまるデータがなければそう出す', async () => {
    mockApiClient.mockResolvedValue({
      headers: ['数量'],
      rows: [],
      total_count: 0,
      unfiltered_count: 0,
    })
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByLabelText('受注明細をすべて選択'))
    expect(await screen.findByText(/絞り込みに当てはまるデータがありません/)).toBeInTheDocument()
  })

  it('ステータスと受注日は最初から条件チップとして並んでいる', () => {
    renderForm()
    expect(screen.getByRole('button', { name: 'ステータスで絞り込む' })).toHaveTextContent(
      'ステータス:すべて'
    )
    expect(screen.getByRole('button', { name: '受注日で絞り込む' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'キーワードで絞り込む' })).not.toBeInTheDocument()
  })

  it('条件チップで絞り込むと、プレビューに条件が渡り「N 件中」と出る', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByLabelText('受注明細をすべて選択'))
    await screen.findByText('A-001')

    await user.click(screen.getByRole('button', { name: 'ステータスで絞り込む' }))
    await user.click(screen.getByRole('option', { name: '製造中' }))

    expect(screen.getByRole('button', { name: 'ステータスで絞り込む' })).toHaveTextContent(
      'ステータス:製造中'
    )
    await waitFor(() =>
      expect(lastPreviewBody()).toMatchObject({ filters: { status: 'manufacturing' } })
    )
    expect(await screen.findByText(/120 件中/)).toBeInTheDocument()

    // ×で条件を外す
    await user.click(screen.getByRole('button', { name: 'ステータスの条件を外す' }))
    await waitFor(() =>
      expect(lastPreviewBody()).toMatchObject({ filters: { status: null } })
    )
  })

  it('「条件を追加」からキーワードを足して絞り込む', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByLabelText('受注明細をすべて選択'))

    await user.click(screen.getByRole('button', { name: '条件を追加' }))
    await user.click(await screen.findByRole('menuitem', { name: 'キーワード' }))
    await user.type(await screen.findByLabelText('キーワード'), '山田')

    expect(screen.getByRole('button', { name: 'キーワードで絞り込む' })).toHaveTextContent(
      '「山田」'
    )
    await waitFor(() => expect(lastPreviewBody()).toMatchObject({ filters: { search: '山田' } }))
  })

  it('表の見出しをクリックすると 昇順 → 降順 → 指定なし の順に並べ替える', async () => {
    const user = userEvent.setup()
    renderForm()
    await user.click(screen.getByLabelText('受注明細をすべて選択'))
    await screen.findByText('A-001')

    const header = () => screen.getByRole('button', { name: '数量' })
    await user.click(header())
    await waitFor(() =>
      expect(lastPreviewBody()).toMatchObject({ sort: { column: 'item_quantity', direction: 'asc' } })
    )
    expect(screen.getByRole('button', { name: '並び順を変える' })).toHaveTextContent('数量（昇順）')

    await user.click(header())
    await waitFor(() =>
      expect(lastPreviewBody()).toMatchObject({ sort: { column: 'item_quantity', direction: 'desc' } })
    )

    await user.click(header())
    await waitFor(() => expect(lastPreviewBody()).toMatchObject({ sort: null }))
  })

  it('出力に失敗したらエラーを出す', async () => {
    mockDownload.mockRejectedValueOnce(new Error('Download failed'))
    const user = userEvent.setup()
    renderForm()

    await user.click(screen.getByLabelText('受注をすべて選択'))
    await user.click(screen.getByRole('button', { name: /CSV を出力/ }))

    expect(toast.error).toHaveBeenCalledWith('CSV の出力に失敗しました')
  })
})

describe('Sidebar', () => {
  it('「データ出力」タブがある', () => {
    render(<Sidebar />)
    const link = screen.getByRole('link', { name: /データ出力/ })
    expect(link).toHaveAttribute('href', '/data-export')
  })
})
