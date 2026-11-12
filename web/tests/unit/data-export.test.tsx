/**
 * データ出力タブ（REQ-0047 / Issue #172）の単体テスト。
 *
 * - 項目が分類ごとに並び、チェックした項目だけがリクエストの列になる
 * - 項目が 0 個なら出力できない
 * - 絞り込み・並べ替えがリクエストに入る
 * - サイドバーに「データ出力」がある
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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

import { downloadFileByPost } from '@/lib/api/client'
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

describe('DataExportForm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('分類ごとに項目が並ぶ', () => {
    render(<DataExportForm columns={columns} />)
    expect(screen.getByText('受注')).toBeInTheDocument()
    expect(screen.getByText('顧客（お届け先）')).toBeInTheDocument()
    expect(screen.getByLabelText('お客様氏名')).toBeInTheDocument()
    expect(screen.getByText('0 / 5 項目を選択中')).toBeInTheDocument()
  })

  it('項目が 0 個のときは出力できない', () => {
    render(<DataExportForm columns={columns} />)
    expect(screen.getByRole('button', { name: /CSV を出力/ })).toBeDisabled()
    expect(screen.getByText('出力する項目を 1 つ以上選んでください')).toBeInTheDocument()
  })

  it('チェックした項目だけを列にして出力する（個人情報は選ばなければ出ない）', async () => {
    const user = userEvent.setup()
    render(<DataExportForm columns={columns} />)

    await user.click(screen.getByLabelText('注文番号'))
    await user.click(screen.getByLabelText('数量'))
    await user.click(screen.getByRole('button', { name: /CSV を出力/ }))

    expect(mockDownload).toHaveBeenCalledTimes(1)
    const [endpoint, body, filename] = mockDownload.mock.calls[0]
    expect(endpoint).toBe('/data-export/csv')
    expect(body).toMatchObject({ columns: ['order_number', 'item_quantity'] })
    expect(filename).toMatch(/^データ出力_\d{8}_\d{6}\.csv$/)
  })

  it('分類のチェックでその分類の項目をまとめて選ぶ・外す', async () => {
    const user = userEvent.setup()
    render(<DataExportForm columns={columns} />)

    const group = screen.getByLabelText('顧客（お届け先）をすべて選択')
    await user.click(group)
    expect(screen.getByLabelText('お客様氏名')).toBeChecked()
    expect(screen.getByLabelText('お届け先電話番号')).toBeChecked()
    expect(screen.getByLabelText('注文番号')).not.toBeChecked()

    await user.click(group)
    expect(screen.getByLabelText('お客様氏名')).not.toBeChecked()
  })

  it('すべて選択・すべて解除', async () => {
    const user = userEvent.setup()
    render(<DataExportForm columns={columns} />)

    await user.click(screen.getByRole('button', { name: 'すべて選択' }))
    expect(screen.getByText('5 / 5 項目を選択中')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'すべて解除' }))
    expect(screen.getByText('0 / 5 項目を選択中')).toBeInTheDocument()
  })

  it('出力に失敗したらエラーを出す', async () => {
    mockDownload.mockRejectedValueOnce(new Error('Download failed'))
    const user = userEvent.setup()
    render(<DataExportForm columns={columns} />)

    await user.click(screen.getByLabelText('注文番号'))
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
