import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SettingsPage from '@/app/(dashboard)/settings/page'

describe('SettingsPage', () => {
  describe('AC-001: メールアドレスが表示される', () => {
    it('設定ページにメールアドレスのラベルが表示される', () => {
      render(<SettingsPage />)

      expect(screen.getByText('メールアドレス')).toBeInTheDocument()
    })

    it('メールアドレス入力フィールドが存在する', () => {
      render(<SettingsPage />)

      const emailInput = screen.getByLabelText('メールアドレス')
      expect(emailInput).toBeInTheDocument()
    })
  })

  describe('AC-002: 名前入力フィールドが存在しない', () => {
    it('名前のラベルが表示されない', () => {
      render(<SettingsPage />)

      expect(screen.queryByText('名前')).not.toBeInTheDocument()
    })

    it('名前入力フィールドが存在しない', () => {
      render(<SettingsPage />)

      expect(screen.queryByLabelText('名前')).not.toBeInTheDocument()
    })
  })

  describe('AC-003: パスワード変更に関する要素が存在しない', () => {
    it('パスワード変更のカードタイトルが表示されない', () => {
      render(<SettingsPage />)

      expect(screen.queryByText('パスワード変更')).not.toBeInTheDocument()
    })

    it('現在のパスワードフィールドが存在しない', () => {
      render(<SettingsPage />)

      expect(screen.queryByLabelText('現在のパスワード')).not.toBeInTheDocument()
    })

    it('新しいパスワードフィールドが存在しない', () => {
      render(<SettingsPage />)

      expect(screen.queryByLabelText('新しいパスワード')).not.toBeInTheDocument()
    })

    it('新しいパスワード（確認）フィールドが存在しない', () => {
      render(<SettingsPage />)

      expect(screen.queryByLabelText('新しいパスワード（確認）')).not.toBeInTheDocument()
    })

    it('パスワードを変更ボタンが存在しない', () => {
      render(<SettingsPage />)

      expect(screen.queryByRole('button', { name: 'パスワードを変更' })).not.toBeInTheDocument()
    })
  })

  describe('AC-004: 保存ボタンが存在しない', () => {
    it('保存ボタンが存在しない', () => {
      render(<SettingsPage />)

      expect(screen.queryByRole('button', { name: '保存' })).not.toBeInTheDocument()
    })
  })
})
