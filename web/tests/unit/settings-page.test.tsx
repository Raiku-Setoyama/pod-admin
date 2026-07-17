import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import SettingsPage from '@/app/(dashboard)/settings/page'
import { apiClient } from '@/lib/api/client'

vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
}))

const mockedApiClient = vi.mocked(apiClient)

describe('SettingsPage - 外部注文の通知', () => {
  beforeEach(() => {
    mockedApiClient.mockReset()
    mockedApiClient.mockResolvedValue(undefined as never)
  })

  it('通知セクションのタイトル・トグル・宛先入力・保存ボタンが表示される', () => {
    render(<SettingsPage />)

    expect(screen.getByText('外部注文の通知')).toBeInTheDocument()
    expect(screen.getByText('通知を有効にする')).toBeInTheDocument()
    expect(screen.getByRole('switch')).toBeInTheDocument()
    expect(screen.getByLabelText('通知先メールアドレス')).toBeInTheDocument()
    // 発送準備日数・注文〆切時間・外部注文の通知 の 3 つの保存ボタン
    expect(screen.getAllByRole('button', { name: '保存' }).length).toBeGreaterThanOrEqual(3)
  })

  it('既存の設定セクション（配送設定・会社休日）も表示される', () => {
    render(<SettingsPage />)

    expect(screen.getByText('配送設定')).toBeInTheDocument()
    expect(screen.getByText('会社休日')).toBeInTheDocument()
  })

  it('有効なメールアドレスを追加するとチップが表示され、削除できる', () => {
    render(<SettingsPage />)

    const input = screen.getByLabelText('通知先メールアドレス')
    fireEvent.change(input, { target: { value: 'staff@example.com' } })
    fireEvent.click(screen.getAllByRole('button', { name: '追加' })[0])

    expect(screen.getByText('staff@example.com')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'staff@example.com を削除' }))
    expect(screen.queryByText('staff@example.com')).not.toBeInTheDocument()
  })

  it('不正なメールアドレスを追加するとエラーが表示され、チップは追加されない', () => {
    render(<SettingsPage />)

    const input = screen.getByLabelText('通知先メールアドレス')
    fireEvent.change(input, { target: { value: 'not-an-email' } })
    fireEvent.click(screen.getAllByRole('button', { name: '追加' })[0])

    expect(
      screen.getByText(/メールアドレスの形式が正しくありません/),
    ).toBeInTheDocument()
    expect(screen.queryByText('not-an-email')).not.toBeInTheDocument()
  })

  it('保存すると有効フラグと宛先の両キーが PUT される', async () => {
    render(<SettingsPage />)

    const input = screen.getByLabelText('通知先メールアドレス')
    fireEvent.change(input, { target: { value: 'staff@example.com' } })
    fireEvent.click(screen.getAllByRole('button', { name: '追加' })[0])

    // 外部注文の通知セクションの保存ボタン（発送準備日数・注文〆切時間の次＝3つ目）
    const saveButtons = screen.getAllByRole('button', { name: '保存' })
    fireEvent.click(saveButtons[2])

    await waitFor(() => {
      expect(mockedApiClient).toHaveBeenCalledWith(
        '/settings/external_order_notification_enabled',
        expect.objectContaining({ method: 'PUT' }),
      )
      expect(mockedApiClient).toHaveBeenCalledWith(
        '/settings/external_order_notification_recipients',
        expect.objectContaining({
          method: 'PUT',
          body: { value: 'staff@example.com' },
        }),
      )
    })
  })
})

describe('SettingsPage - 注文〆切時間', () => {
  beforeEach(() => {
    mockedApiClient.mockReset()
    mockedApiClient.mockResolvedValue(undefined as never)
  })

  it('配送設定カード内に注文〆切時間の入力欄が表示される', () => {
    render(<SettingsPage />)

    expect(screen.getByText('注文〆切時間')).toBeInTheDocument()
    expect(screen.getByLabelText('注文〆切時間')).toBeInTheDocument()
  })

  it('時刻を入力して保存すると order_deadline_time が PUT される', async () => {
    render(<SettingsPage />)

    const input = screen.getByLabelText('注文〆切時間')
    fireEvent.change(input, { target: { value: '18:00' } })

    // 保存ボタン: 発送準備日数(0) / 注文〆切時間(1) / 通知(2)
    const saveButtons = screen.getAllByRole('button', { name: '保存' })
    fireEvent.click(saveButtons[1])

    await waitFor(() => {
      expect(mockedApiClient).toHaveBeenCalledWith(
        '/settings/order_deadline_time',
        expect.objectContaining({ method: 'PUT', body: { value: '18:00' } }),
      )
    })
  })

  it('空欄のまま保存すると空文字が PUT され無効化できる', async () => {
    render(<SettingsPage />)

    const saveButtons = screen.getAllByRole('button', { name: '保存' })
    fireEvent.click(saveButtons[1])

    await waitFor(() => {
      expect(mockedApiClient).toHaveBeenCalledWith(
        '/settings/order_deadline_time',
        expect.objectContaining({ method: 'PUT', body: { value: '' } }),
      )
    })
  })

  it('API が 422 を返すとエラーメッセージを表示する', async () => {
    mockedApiClient.mockRejectedValueOnce(
      new Error('注文〆切時間は HH:MM 形式（00:00〜23:59）で指定してください'),
    )
    render(<SettingsPage />)

    const input = screen.getByLabelText('注文〆切時間')
    fireEvent.change(input, { target: { value: '18:00' } })
    const saveButtons = screen.getAllByRole('button', { name: '保存' })
    fireEvent.click(saveButtons[1])

    expect(
      await screen.findByText(/注文〆切時間は HH:MM 形式/),
    ).toBeInTheDocument()
  })
})
