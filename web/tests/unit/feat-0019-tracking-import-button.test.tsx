/**
 * Unit tests for FEAT-0019: 伝票番号インポートボタンのモーダル統合
 *
 * Covers:
 * - AC-001: 「伝票番号インポート」ボタンをクリックするとモーダルダイアログが開く
 * - AC-002: モーダル内に TrackingImport コンポーネントが正しく表示される
 * - AC-003: モーダルの閉じるボタン（X）またはオーバーレイクリックでモーダルが閉じる
 * - AC-004: インポート成功後に配送一覧が自動リフレッシュされる
 * - AC-005: モーダルを再度開いた際に前回の状態がリセットされている
 * - AC-006: モーダルのタイトルに「伝票番号インポート」と表示される
 *
 * NOTE: TDD Red phase - tests will fail until implementation is completed.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

// ======================================
// Mocks
// ======================================

// Mock API client
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  downloadFile: vi.fn(),
}))

// Mock sonner
vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

// Mock useShipments hook - returns stable data and a trackable mutate function
const mockMutate = vi.fn()
vi.mock('@/features/shipments/hooks/use-shipments', () => ({
  useShipments: () => ({
    shipments: [],
    total: 0,
    page: 1,
    limit: 20,
    isLoading: false,
    error: null,
    mutate: mockMutate,
  }),
}))

// Mock SWR (needed because useShipments internally uses it)
vi.mock('swr', () => ({
  default: vi.fn(() => ({
    data: null,
    error: null,
    isLoading: false,
    mutate: vi.fn(),
  })),
}))

// Mock child components that are not under test to simplify rendering
vi.mock('@/features/shipments/components/shipment-list', () => ({
  ShipmentList: () => <div data-testid="mock-shipment-list">ShipmentList</div>,
}))

vi.mock('@/features/shipments/components/shipment-filters', () => ({
  ShipmentFilters: () => <div data-testid="mock-shipment-filters">ShipmentFilters</div>,
}))

vi.mock('@/components/common/pagination', () => ({
  Pagination: () => <div data-testid="mock-pagination">Pagination</div>,
}))

vi.mock('@/components/common/loading-spinner', () => ({
  PageLoading: () => <div data-testid="mock-page-loading">Loading...</div>,
}))

vi.mock('@/constants/status', () => ({
  getShipmentStatusUpdateOptions: () => [
    { value: 'ready', label: '出荷準備中' },
    { value: 'shipped', label: '発送済み' },
  ],
}))

// Import the page component AFTER mocks are set up
import ShipmentsPage from '@/app/(dashboard)/shipments/page'

// ======================================
// AC-001: 「伝票番号インポート」ボタンをクリックするとモーダルダイアログが開く
// ======================================

describe('AC-001: Clicking the tracking import button opens a modal dialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the tracking import button', () => {
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    expect(importButton).toBeInTheDocument()
  })

  it('opens a dialog when the tracking import button is clicked', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // The dialog should be visible with role="dialog"
    const dialog = screen.getByRole('dialog')
    expect(dialog).toBeInTheDocument()
  })

  it('the dialog contains the TrackingImport component (file input present)', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // TrackingImport renders a file input
    const fileInput = document.querySelector('input[type="file"]')
    expect(fileInput).toBeInTheDocument()
  })
})

// ======================================
// AC-002: モーダル内に TrackingImport コンポーネントが正しく表示される
// ======================================

describe('AC-002: TrackingImport component is correctly displayed inside the modal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a file input for CSV/XLSX upload inside the modal', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(fileInput).toBeInTheDocument()
    expect(fileInput.getAttribute('accept')).toContain('.csv')
    expect(fileInput.getAttribute('accept')).toContain('.xlsx')
  })

  it('shows the template download link inside the modal', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    const templateLink = screen.getByText(/テンプレート/)
    expect(templateLink).toBeInTheDocument()
  })

  it('shows the import execution button inside the modal', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // Inside the dialog there should be an "インポート" button (the TrackingImport submit button)
    const dialog = screen.getByRole('dialog')
    const importExecButton = dialog.querySelector('button')
    // Look for the import button text within the dialog
    expect(screen.getAllByText(/インポート/).length).toBeGreaterThanOrEqual(2)
  })
})

// ======================================
// AC-003: モーダルの閉じるボタン（X）でモーダルが閉じる
// ======================================

describe('AC-003: Modal closes via close button (X)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('closes the dialog when the X close button is clicked', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    // Open the modal
    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // Dialog should be visible
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    // Find and click the close button (rendered as "Close" in sr-only text by shadcn Dialog)
    const closeButton = screen.getByRole('button', { name: /Close/ })
    await user.click(closeButton)

    // Dialog should no longer be visible
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})

// ======================================
// AC-004: インポート成功後に配送一覧が自動リフレッシュされる
// ======================================

describe('AC-004: Shipment list auto-refreshes after successful import', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls mutate() when onImportComplete is triggered after import success', async () => {
    const user = userEvent.setup()

    // Mock the apiClient to return a successful import result
    const { apiClient: mockApiClient } = await import('@/lib/api/client')
    const mockedApiClient = vi.mocked(mockApiClient)
    mockedApiClient.mockResolvedValueOnce({
      total_count: 1,
      success_count: 1,
      error_count: 0,
      errors: [],
      updated_shipments: [],
    })

    render(<ShipmentsPage />)

    // Open the modal
    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // Select a file
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const csvFile = new File(
      ['注文番号,伝票番号,運送会社名\nORD-001,1234-5678-9012,ヤマト運輸'],
      'tracking.csv',
      { type: 'text/csv' }
    )
    await user.upload(fileInput, csvFile)

    // Click the import button inside the dialog
    // The TrackingImport component renders a button with text "インポート"
    const dialog = screen.getByRole('dialog')
    const buttons = dialog.querySelectorAll('button')
    // Find the button that says "インポート" (not "伝票番号インポート")
    let importExecButton: HTMLButtonElement | null = null
    buttons.forEach((btn) => {
      if (btn.textContent?.includes('インポート') && !btn.textContent?.includes('伝票番号')) {
        importExecButton = btn
      }
    })
    expect(importExecButton).not.toBeNull()
    await user.click(importExecButton!)

    // After successful import, mutate() should be called to refresh the shipment list
    await waitFor(() => {
      expect(mockMutate).toHaveBeenCalled()
    })
  })
})

// ======================================
// AC-005: モーダルを再度開いた際に前回の状態がリセットされている
// ======================================

describe('AC-005: Modal state resets when reopened', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('resets TrackingImport internal state when modal is closed and reopened (via key increment)', async () => {
    const user = userEvent.setup()

    // Mock the apiClient to return a successful import result
    const { apiClient: mockApiClient } = await import('@/lib/api/client')
    const mockedApiClient = vi.mocked(mockApiClient)
    mockedApiClient.mockResolvedValueOnce({
      total_count: 1,
      success_count: 1,
      error_count: 0,
      errors: [],
      updated_shipments: [],
    })

    render(<ShipmentsPage />)

    // Open the modal the first time
    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // Select a file
    const fileInput = document.querySelector('input[type="file"]') as HTMLInputElement
    const csvFile = new File(
      ['注文番号,伝票番号,運送会社名\nORD-001,1234-5678-9012,ヤマト運輸'],
      'tracking.csv',
      { type: 'text/csv' }
    )
    await user.upload(fileInput, csvFile)

    // Click import to execute
    const dialog = screen.getByRole('dialog')
    const buttons = dialog.querySelectorAll('button')
    let importExecButton: HTMLButtonElement | null = null
    buttons.forEach((btn) => {
      if (btn.textContent?.includes('インポート') && !btn.textContent?.includes('伝票番号')) {
        importExecButton = btn
      }
    })
    if (importExecButton) {
      await user.click(importExecButton)
    }

    // Wait for the result to appear
    await waitFor(() => {
      expect(screen.getByText(/1件/)).toBeInTheDocument()
    })

    // Close the modal
    const closeButton = screen.getByRole('button', { name: /Close/ })
    await user.click(closeButton)

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    // Reopen the modal
    await user.click(importButton)

    // After reopening, the previous result should be gone (state reset via key prop)
    await waitFor(() => {
      const dialog2 = screen.getByRole('dialog')
      expect(dialog2).toBeInTheDocument()
    })

    // The "選択中:" text (showing file name) should not be present
    expect(screen.queryByText(/選択中:/)).not.toBeInTheDocument()

    // The import result text should not be present
    expect(screen.queryByText(/インポート完了/)).not.toBeInTheDocument()
  })
})

// ======================================
// AC-006: モーダルのタイトルに「伝票番号インポート」と表示される
// ======================================

describe('AC-006: Modal title displays "伝票番号インポート"', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows "伝票番号インポート" as the dialog title', async () => {
    const user = userEvent.setup()
    render(<ShipmentsPage />)

    const importButton = screen.getByRole('button', { name: /伝票番号インポート/ })
    await user.click(importButton)

    // The DialogTitle should contain "伝票番号インポート"
    const dialog = screen.getByRole('dialog')
    // DialogTitle renders with role="heading" inside the dialog
    const heading = dialog.querySelector('[data-slot="dialog-title"]')
      ?? dialog.querySelector('h2')
    expect(heading).toBeInTheDocument()
    expect(heading?.textContent).toContain('伝票番号インポート')
  })
})
