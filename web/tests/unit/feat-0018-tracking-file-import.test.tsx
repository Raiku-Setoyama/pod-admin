/**
 * Unit tests for FEAT-0018: CSV/XLSXファイルによる伝票番号一括インポート
 *
 * Covers:
 * - AC-014: ファイル選択してインポート実行 -> API呼び出し -> 結果表示
 * - AC-015: インポート成功後に配送一覧が自動リフレッシュされる
 * - AC-016: サンプルテンプレートダウンロードリンクが表示される
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// Mock API client
const mockApiClient = vi.fn()
vi.mock('@/lib/api/client', () => ({
  apiClient: (...args: unknown[]) => mockApiClient(...args),
  downloadFile: vi.fn(),
}))

// Mock sonner
const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
}
vi.mock('sonner', () => ({
  toast: mockToast,
}))

// Import the component AFTER mocks are set up
// The component will be renamed from TrackingImport to a file-upload-based dialog
import { TrackingImport } from '@/features/shipments/components/tracking-import'
import type { TrackingFileImportResult } from '@/types/api'

// ======================================
// Helper: Create a mock File
// ======================================

function createMockFile(
  name: string,
  content: string = 'test',
  type: string = 'text/csv'
): File {
  return new File([content], name, { type })
}

function createMockCSVFile(
  rows: string[][] = [
    ['注文番号', '伝票番号', '運送会社名'],
    ['ORD-001', '1234-5678-9012', 'ヤマト運輸'],
  ]
): File {
  const csvContent = rows.map((row) => row.join(',')).join('\n')
  return new File([csvContent], 'tracking.csv', { type: 'text/csv' })
}

// ======================================
// Helper: Mock successful import response
// ======================================

function createMockImportResult(
  overrides: Partial<TrackingFileImportResult> = {}
): TrackingFileImportResult {
  return {
    total_count: 1,
    success_count: 1,
    error_count: 0,
    email_sent_count: 0,
    email_failed_count: 0,
    errors: [],
    results: [],
    updated_shipments: [],
    ...overrides,
  }
}

// ======================================
// AC-014: ファイル選択してインポート実行 -> API呼び出し -> 結果表示
// ======================================

describe('AC-014: File upload import dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the file upload area', () => {
    render(<TrackingImport />)

    // ファイルアップロード UI が存在すること
    // ファイル選択用のinput[type="file"]またはドロップゾーンが存在
    const fileInput = document.querySelector('input[type="file"]')
    expect(fileInput).toBeInTheDocument()
  })

  it('renders the import button', () => {
    render(<TrackingImport />)

    // インポートボタンが存在すること
    const importButton = screen.getByRole('button', { name: /インポート/ })
    expect(importButton).toBeInTheDocument()
  })

  it('accepts CSV files', () => {
    render(<TrackingImport />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    expect(fileInput).toBeInTheDocument()

    // accept属性でCSV/XLSXが許可されていること
    const accept = fileInput?.getAttribute('accept') ?? ''
    expect(accept).toContain('.csv')
  })

  it('accepts XLSX files', () => {
    render(<TrackingImport />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    expect(fileInput).toBeInTheDocument()

    const accept = fileInput?.getAttribute('accept') ?? ''
    expect(accept).toContain('.xlsx')
  })

  it('calls API with FormData when file is selected and import is clicked', async () => {
    const user = userEvent.setup()
    mockApiClient.mockResolvedValueOnce(createMockImportResult())

    render(<TrackingImport />)

    // ファイルを選択
    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const csvFile = createMockCSVFile()
    await user.upload(fileInput, csvFile)

    // インポートボタンをクリック
    const importButton = screen.getByRole('button', { name: /インポート/ })
    await user.click(importButton)

    // API が呼ばれたことを確認
    await waitFor(() => {
      expect(mockApiClient).toHaveBeenCalledWith(
        '/shipments/import',
        expect.objectContaining({
          method: 'POST',
        })
      )
    })
  })

  it('displays success count after successful import', async () => {
    const user = userEvent.setup()
    mockApiClient.mockResolvedValueOnce(
      createMockImportResult({
        total_count: 3,
        success_count: 3,
        error_count: 0,
      })
    )

    render(<TrackingImport />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const csvFile = createMockCSVFile()
    await user.upload(fileInput, csvFile)

    const importButton = screen.getByRole('button', { name: /インポート/ })
    await user.click(importButton)

    // 成功件数が表示されること
    await waitFor(() => {
      expect(screen.getByText(/3件/)).toBeInTheDocument()
    })
  })

  it('displays error details when some rows fail', async () => {
    const user = userEvent.setup()
    mockApiClient.mockResolvedValueOnce(
      createMockImportResult({
        total_count: 2,
        success_count: 1,
        error_count: 1,
        errors: [
          {
            row: 2,
            order_number: 'ORD-999',
            message: '注文番号が見つかりません',
          },
        ],
      })
    )

    render(<TrackingImport />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const csvFile = createMockCSVFile()
    await user.upload(fileInput, csvFile)

    const importButton = screen.getByRole('button', { name: /インポート/ })
    await user.click(importButton)

    // エラー詳細が表示されること
    await waitFor(() => {
      expect(screen.getByText(/ORD-999/)).toBeInTheDocument()
      expect(screen.getByText(/注文番号が見つかりません/)).toBeInTheDocument()
    })
  })

  it('displays error count in the result', async () => {
    const user = userEvent.setup()
    mockApiClient.mockResolvedValueOnce(
      createMockImportResult({
        total_count: 2,
        success_count: 1,
        error_count: 1,
        errors: [
          {
            row: 2,
            order_number: 'ORD-999',
            message: '注文番号が見つかりません',
          },
        ],
      })
    )

    render(<TrackingImport />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const csvFile = createMockCSVFile()
    await user.upload(fileInput, csvFile)

    const importButton = screen.getByRole('button', { name: /インポート/ })
    await user.click(importButton)

    // 失敗件数が表示されること
    await waitFor(() => {
      expect(screen.getByText(/1件.*失敗|失敗.*1/)).toBeInTheDocument()
    })
  })
})

// ======================================
// AC-015: インポート成功後に配送一覧が自動リフレッシュされる
// ======================================

describe('AC-015: Auto-refresh shipment list after successful import', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls onImportComplete callback after successful import', async () => {
    const user = userEvent.setup()
    const onImportComplete = vi.fn()
    mockApiClient.mockResolvedValueOnce(createMockImportResult())

    render(<TrackingImport onImportComplete={onImportComplete} />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const csvFile = createMockCSVFile()
    await user.upload(fileInput, csvFile)

    const importButton = screen.getByRole('button', { name: /インポート/ })
    await user.click(importButton)

    // onImportComplete が呼ばれたことを確認（リフレッシュのトリガー）
    await waitFor(() => {
      expect(onImportComplete).toHaveBeenCalledTimes(1)
    })
  })

  it('does not call onImportComplete when import fails completely', async () => {
    const user = userEvent.setup()
    const onImportComplete = vi.fn()
    mockApiClient.mockRejectedValueOnce(new Error('API Error'))

    render(<TrackingImport onImportComplete={onImportComplete} />)

    const fileInput = document.querySelector(
      'input[type="file"]'
    ) as HTMLInputElement
    const csvFile = createMockCSVFile()
    await user.upload(fileInput, csvFile)

    const importButton = screen.getByRole('button', { name: /インポート/ })
    await user.click(importButton)

    // API エラー時は onImportComplete が呼ばれないこと
    await waitFor(() => {
      expect(onImportComplete).not.toHaveBeenCalled()
    })
  })
})

// ======================================
// AC-016: サンプルテンプレートダウンロードリンクが表示される
// ======================================

describe('AC-016: Sample template download link is displayed', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders a template download link', () => {
    render(<TrackingImport />)

    // テンプレートダウンロードリンクが存在すること
    const downloadLink = screen.getByText(/テンプレート/)
    expect(downloadLink).toBeInTheDocument()
  })

  it('template download link points to the import-template endpoint', () => {
    render(<TrackingImport />)

    // テンプレートダウンロードリンクがimport-templateエンドポイントを参照していること
    const downloadLink = screen.getByText(/テンプレート/)
    // リンクまたはボタンとして存在
    expect(downloadLink).toBeInTheDocument()

    // href属性またはonClickでimport-templateを参照
    const linkElement = downloadLink.closest('a')
    if (linkElement) {
      expect(linkElement.getAttribute('href')).toContain('import-template')
    }
    // If it's a button, it should trigger a download via API
  })
})
