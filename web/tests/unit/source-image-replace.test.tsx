/**
 * 元画像差し替え UI のテスト
 *
 * 製造データの元画像（PNGレイヤー）を管理画面から差し替えられることを検証する。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SourceImageReplaceDialog } from '@/features/manufacturing-data/source-image-replace-dialog'
import {
  canRegenerateManufacturingData,
  canReplaceSourceImages,
  ManufacturingRegenerateControls,
} from '@/features/manufacturing-data/regenerate-controls'
import { ApiError, apiClient, fetchBlob } from '@/lib/api/client'
import type { ManufacturingDataDetail } from '@/types/api'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  fetchBlob: vi.fn(),
  // apiClient が投げる例外クラス（ダイアログは instanceof で判定する）
  ApiError: class ApiError extends Error {
    constructor(
      public status: number,
      public code: string,
      message: string
    ) {
      super(message)
    }
  },
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

const mockedApiClient = vi.mocked(apiClient)
const mockedFetchBlob = vi.mocked(fetchBlob)

const detail: ManufacturingDataDetail = {
  id: 'md-1',
  product_code: 'RKSYO-1',
  product_type: 'acrylic_keychain',
  size: '50x50mm',
  variant: 'clear',
  status: 'failed',
  output_filename: null,
  file_size: null,
  error_message: 'VM error',
  source_images: [
    { layer_type: 'color', origin: 'external', url: 'https://x/color.png', filename: null },
    { layer_type: 'cutline', origin: 'uploaded', url: null, filename: 'cutline_fix.png' },
  ],
  source_images_replaced_at: '2026-07-26T10:00:00Z',
  source_images_replaced_by: 'admin@example.com',
}

function pngFile(name = 'new_color.png'): File {
  return new File([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], name, { type: 'image/png' })
}

describe('canReplaceSourceImages', () => {
  it('製造着手前かつ生成中でない v2 明細は差し替え可能', () => {
    expect(canReplaceSourceImages('preparing_order', 'failed', 'md-1')).toBe(true)
    expect(canReplaceSourceImages('ordered', 'ready', 'md-1')).toBe(true)
    // 生成待ちも是正できる（再作成は不可だが差し替えは可能）
    expect(canReplaceSourceImages('preparing_order', 'pending', 'md-1')).toBe(true)
    expect(canRegenerateManufacturingData('preparing_order', 'pending', 'md-1')).toBe(false)
  })

  it('生成中・製造着手後・v1 明細は差し替え不可', () => {
    expect(canReplaceSourceImages('preparing_order', 'generating', 'md-1')).toBe(false)
    expect(canReplaceSourceImages('manufacturing', 'ready', 'md-1')).toBe(false)
    expect(canReplaceSourceImages('delivered', 'ready', 'md-1')).toBe(false)
    expect(canReplaceSourceImages('ordered', null, null)).toBe(false)
  })
})

describe('ManufacturingRegenerateControls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('差し替え可能な明細に「元画像差し替え」ボタンを表示する', () => {
    render(
      <ManufacturingRegenerateControls
        itemStatus="preparing_order"
        mfgStatus="failed"
        manufacturingDataId="md-1"
        regeneratingId={null}
        onRegenerate={vi.fn()}
      />
    )
    expect(screen.getByRole('button', { name: /元画像差し替え/ })).toBeInTheDocument()
  })

  it('差し替え済みの明細にはバッジを表示する', () => {
    render(
      <ManufacturingRegenerateControls
        itemStatus="ordered"
        mfgStatus="ready"
        manufacturingDataId="md-1"
        sourceImagesReplacedAt="2026-07-26T10:00:00Z"
        regeneratingId={null}
        onRegenerate={vi.fn()}
      />
    )
    expect(screen.getByText('元画像差し替え済み')).toBeInTheDocument()
  })
})

describe('SourceImageReplaceDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedFetchBlob.mockResolvedValue(new Blob([new Uint8Array([0x89])], { type: 'image/png' }))
  })

  it('現在のレイヤー構成を由来つきで表示する', async () => {
    mockedApiClient.mockResolvedValue(detail)

    render(
      <SourceImageReplaceDialog manufacturingDataId="md-1" open onClose={vi.fn()} />
    )

    await waitFor(() =>
      expect(mockedApiClient).toHaveBeenCalledWith('/manufacturing-data/md-1')
    )
    expect(await screen.findByText('カラー')).toBeInTheDocument()
    expect(screen.getByText('カットライン')).toBeInTheDocument()
    // 外部受注由来は元画像へのリンク、差し替え済みはファイル名を表示
    expect(screen.getByRole('link', { name: /受注時の元画像を開く/ })).toHaveAttribute(
      'href',
      'https://x/color.png'
    )
    expect(screen.getByText('cutline_fix.png')).toBeInTheDocument()
    expect(screen.getByText('差し替え済み')).toBeInTheDocument()
  })

  it('選択したレイヤーだけを multipart で送信し、完了後にコールバックを呼ぶ', async () => {
    mockedApiClient.mockResolvedValue(detail)
    const onReplaced = vi.fn()
    const onClose = vi.fn()

    render(
      <SourceImageReplaceDialog
        manufacturingDataId="md-1"
        open
        onClose={onClose}
        onReplaced={onReplaced}
      />
    )
    await screen.findByText('カラー')

    const input = screen.getByLabelText('カラーの元画像を選択') as HTMLInputElement
    await userEvent.upload(input, pngFile())

    await userEvent.click(screen.getByRole('button', { name: /差し替えて再生成/ }))

    await waitFor(() => expect(onReplaced).toHaveBeenCalled())
    const [endpoint, options] = mockedApiClient.mock.calls.at(-1) as [
      string,
      { method: string; body: FormData },
    ]
    expect(endpoint).toBe('/manufacturing-data/md-1/source-images')
    expect(options.method).toBe('POST')
    expect((options.body.get('color') as File).name).toBe('new_color.png')
    expect(onClose).toHaveBeenCalled()
  })

  it('ファイル未選択のうちは送信ボタンを押せない', async () => {
    mockedApiClient.mockResolvedValue(detail)

    render(
      <SourceImageReplaceDialog manufacturingDataId="md-1" open onClose={vi.fn()} />
    )
    await screen.findByText('カラー')

    expect(screen.getByRole('button', { name: /差し替えて再生成/ })).toBeDisabled()
  })

  it.each([
    [409, 'conflict', /製造中\/納品済みの注文と共有/],
    [400, '元画像は PNG 形式のみ対応しています: color', '元画像は PNG 形式のみ対応しています: color'],
  ])('%i の場合はエラー内容を表示する', async (status, message, expected) => {
    mockedApiClient.mockResolvedValue(detail)

    render(
      <SourceImageReplaceDialog manufacturingDataId="md-1" open onClose={vi.fn()} />
    )
    await screen.findByText('カラー')
    await userEvent.upload(
      screen.getByLabelText('カラーの元画像を選択') as HTMLInputElement,
      pngFile()
    )

    mockedApiClient.mockRejectedValueOnce(new ApiError(status, 'ERR', message))
    await userEvent.click(screen.getByRole('button', { name: /差し替えて再生成/ }))

    expect(await screen.findByText(expected)).toBeInTheDocument()
  })
})
