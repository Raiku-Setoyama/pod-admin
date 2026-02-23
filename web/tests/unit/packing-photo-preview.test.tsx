/**
 * PackingPhotoPreview のテスト
 *
 * FEAT-0003: 管理者が配送詳細画面でアップロード済みの梱包写真をプレビュー表示できる
 *
 * このテストは、梱包写真プレビューコンポーネントの動作を検証します。
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { PackingPhotoPreview } from '@/features/shipments/components/packing-photo-preview'

// API クライアントをモック
vi.mock('@/lib/api/client', () => ({
  apiClient: vi.fn(),
  getApiBaseUrl: vi.fn(() => 'http://localhost:8000/api/v1'),
}))

describe('PackingPhotoPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('サムネイル表示の検証', () => {
    it('AC-005: 梱包写真が存在する場合、サムネイル画像が表示される', () => {
      const shipmentId = 'test-shipment-123'
      const packingPhotoPath = 'shipments/test-shipment-123/photo.jpg'

      render(
        <PackingPhotoPreview
          shipmentId={shipmentId}
          packingPhotoPath={packingPhotoPath}
        />
      )

      // サムネイル画像が表示されることを確認
      const thumbnail = screen.getByRole('img', { name: /梱包写真/i })
      expect(thumbnail).toBeInTheDocument()

      // 画像のsrc属性がAPIエンドポイントを指していることを確認
      expect(thumbnail).toHaveAttribute(
        'src',
        expect.stringContaining(`/shipments/${shipmentId}/packing-photo`)
      )
    })

    it('AC-008: 梱包写真が存在しない場合はアップロードボタンのみ表示される', () => {
      const shipmentId = 'test-shipment-123'

      render(
        <PackingPhotoPreview
          shipmentId={shipmentId}
          packingPhotoPath={null}
        />
      )

      // サムネイル画像が表示されないことを確認
      const thumbnail = screen.queryByRole('img', { name: /梱包写真/i })
      expect(thumbnail).not.toBeInTheDocument()

      // アップロードボタンまたはメッセージが表示されることを確認
      const uploadButton = screen.getByRole('button', { name: /写真を選択|アップロード/i })
      expect(uploadButton).toBeInTheDocument()
    })
  })

  describe('拡大モーダルの検証', () => {
    it('AC-006: サムネイルクリックで拡大モーダルが開く', async () => {
      const user = userEvent.setup()
      const shipmentId = 'test-shipment-123'
      const packingPhotoPath = 'shipments/test-shipment-123/photo.jpg'

      render(
        <PackingPhotoPreview
          shipmentId={shipmentId}
          packingPhotoPath={packingPhotoPath}
        />
      )

      // サムネイルをクリック
      const thumbnail = screen.getByRole('img', { name: /梱包写真/i })
      await user.click(thumbnail)

      // モーダルが開くことを確認
      const modal = screen.getByRole('dialog')
      expect(modal).toBeInTheDocument()

      // フルサイズ画像が表示されることを確認
      const fullSizeImage = screen.getByRole('img', { name: /拡大/i })
      expect(fullSizeImage).toBeInTheDocument()
    })

    it('AC-007: 拡大モーダルを閉じることができる（閉じるボタン）', async () => {
      const user = userEvent.setup()
      const shipmentId = 'test-shipment-123'
      const packingPhotoPath = 'shipments/test-shipment-123/photo.jpg'

      render(
        <PackingPhotoPreview
          shipmentId={shipmentId}
          packingPhotoPath={packingPhotoPath}
        />
      )

      // サムネイルをクリックしてモーダルを開く
      const thumbnail = screen.getByRole('img', { name: /梱包写真/i })
      await user.click(thumbnail)

      // モーダルが開いていることを確認
      expect(screen.getByRole('dialog')).toBeInTheDocument()

      // 閉じるボタンをクリック
      const closeButton = screen.getByRole('button', { name: /閉じる|close/i })
      await user.click(closeButton)

      // モーダルが閉じることを確認
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      })
    })
  })

  describe('ローディングとエラー状態の検証', () => {
    it('AC-009: 画像読み込み中はローディング状態を表示', () => {
      const shipmentId = 'test-shipment-123'
      const packingPhotoPath = 'shipments/test-shipment-123/photo.jpg'

      render(
        <PackingPhotoPreview
          shipmentId={shipmentId}
          packingPhotoPath={packingPhotoPath}
        />
      )

      // ローディングインジケータが表示されることを確認
      // 注: 画像読み込み中の状態をテストするため、初期レンダリング時に確認
      const loadingIndicator = screen.queryByTestId('loading-indicator') ||
        screen.queryByRole('progressbar') ||
        screen.queryByText(/読み込み中|loading/i)

      // ローディング状態の何らかの表示があることを確認
      // 実装によってはスケルトンやスピナーなど
      expect(
        loadingIndicator ||
        screen.queryByTestId('photo-skeleton') ||
        screen.queryByTestId('photo-loading')
      ).toBeInTheDocument()
    })

    it('AC-010: 画像読み込みエラー時はエラーメッセージを表示', async () => {
      const shipmentId = 'test-shipment-123'
      const packingPhotoPath = 'shipments/test-shipment-123/photo.jpg'

      render(
        <PackingPhotoPreview
          shipmentId={shipmentId}
          packingPhotoPath={packingPhotoPath}
        />
      )

      // 画像のエラーイベントをシミュレート
      const thumbnail = screen.getByRole('img', { name: /梱包写真/i })
      fireEvent.error(thumbnail)

      // エラーメッセージが表示されることを確認
      await waitFor(() => {
        const errorMessage = screen.getByText(/画像の読み込みに失敗|エラー/i)
        expect(errorMessage).toBeInTheDocument()
      })
    })
  })
})
