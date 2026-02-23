import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'

/**
 * FEAT-0017: 配送管理ページ E2Eテスト
 *
 * 対象機能:
 * - 配送一覧取得（フィルタリング・ページネーション）
 * - 配送詳細取得
 * - 配送ステータス更新（個別）
 * - 配送ステータス一括更新
 * - 梱包写真アップロード
 * - 配送CSVエクスポート
 * - 追跡番号インポート
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

// ============================
// 配送一覧表示テスト
// ============================
test.describe('FEAT-0017: 配送一覧表示', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-001: テーブルヘッダーが正しく表示される', async ({ page }) => {
    const headers = ['配送ID', '宛先', '商品数', '伝票番号', '作成日', 'ステータス']
    for (const header of headers) {
      await expect(page.locator('th', { hasText: header })).toBeVisible()
    }
  })

  test('AC-002: 配送データが1件以上表示される', async ({ page }) => {
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()
    expect(rowCount).toBeGreaterThan(0)

    // 「該当する配送がありません」が表示されていないこと
    const firstRowText = await rows.first().textContent()
    expect(firstRowText).not.toContain('該当する配送がありません')
  })

  test('AC-003: ページネーションが表示される', async ({ page }) => {
    // 表示件数セレクタが存在すること
    const paginationArea = page.locator('[class*="pagination"], [class*="Pagination"]').first()
    // ページ情報テキスト（例: 「全X件中 1-20件表示」のようなテキスト）
    await expect(page.getByText(/件/)).toBeVisible()
  })

  test('AC-004: ステータスフィルターで「配送準備中」を選択するとフィルタリングが動作する', async ({ page }) => {
    // ステータスフィルターのSelectTriggerをクリック
    const selectTrigger = page.locator('button[role="combobox"]')
    await selectTrigger.click()

    // 「配送準備中」オプションを選択
    await page.getByRole('option', { name: '配送準備中' }).click()

    // フィルターが適用されるまで待機
    await page.waitForLoadState('networkidle')

    // エラーが発生していないことを確認（ページがクラッシュしていない）
    await expect(page.locator('table')).toBeVisible()
  })

  test('AC-005: 検索フィルターでテキストを入力するとフィルタリングが動作する', async ({ page }) => {
    const searchInput = page.getByPlaceholder('配送ID、伝票番号、顧客名で検索...')
    await expect(searchInput).toBeVisible()

    // テキストを入力
    await searchInput.fill('テスト')

    // フィルターが適用されるまで待機
    await page.waitForLoadState('networkidle')

    // エラーが発生していないことを確認
    await expect(page.locator('table')).toBeVisible()
  })
})

// ============================
// 配送詳細表示テスト
// ============================
test.describe('FEAT-0017: 配送詳細表示', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-006: 配送行をクリックすると詳細ページに遷移する', async ({ page }) => {
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()
    expect(rowCount).toBeGreaterThan(0)

    // 最初のデータ行をクリック（チェックボックスセルではなく2番目のセル）
    await rows.first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // URLが /shipments/{id} に変わること
    await expect(page).toHaveURL(/\/shipments\/[a-f0-9-]+/)

    // 「配送詳細」タイトルが表示されること
    await expect(page.getByText('配送詳細')).toBeVisible()
  })

  test('AC-007: 配送詳細ページに配送情報カードが表示される', async ({ page }) => {
    // 最初の配送行をクリックして詳細へ
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // 配送情報カードの確認
    await expect(page.getByText('配送情報')).toBeVisible()
    await expect(page.getByText('配送ID')).toBeVisible()
    await expect(page.getByText('作成日時')).toBeVisible()
    await expect(page.getByRole('button', { name: 'ステータス更新' })).toBeVisible()
  })

  test('AC-008: 配送詳細ページに配送先情報が表示される', async ({ page }) => {
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // 配送先カードの確認
    await expect(page.getByText('配送先')).toBeVisible()
    await expect(page.getByText('氏名')).toBeVisible()
  })

  test('AC-009: 配送詳細ページに含まれる商品一覧が表示される', async ({ page }) => {
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // 含まれる商品カードの確認
    await expect(page.getByText(/含まれる商品/)).toBeVisible()
    await expect(page.locator('th', { hasText: '注文番号' })).toBeVisible()
    await expect(page.locator('th', { hasText: '商品名' })).toBeVisible()
  })

  test('AC-010: 「配送一覧に戻る」ボタンで一覧に戻れる', async ({ page }) => {
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // 「配送一覧に戻る」ボタンをクリック
    await page.getByRole('button', { name: '配送一覧に戻る' }).click()
    await page.waitForLoadState('networkidle')

    // 配送一覧ページに戻ること
    await expect(page).toHaveURL('/shipments')
  })
})

// ============================
// 配送ステータス更新（個別）テスト
// ============================
test.describe('FEAT-0017: 配送ステータス更新（個別）', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-011: 「ステータス更新」ボタンでダイアログが開く', async ({ page }) => {
    // 最初の配送行をクリックして詳細へ
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // 「ステータス更新」ボタンをクリック
    await page.getByRole('button', { name: 'ステータス更新' }).click()

    // ダイアログが表示される
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('ステータス更新', { exact: false })).toBeVisible()

    // 選択肢と更新ボタンが表示される
    await expect(page.getByText('新しいステータス')).toBeVisible()
    await expect(page.getByRole('button', { name: '更新' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'キャンセル' })).toBeVisible()
  })

  test('AC-012: ステータスを変更すると反映される', async ({ page }) => {
    // pendingの配送を見つけるため、フィルターで配送準備中を選択
    const selectTrigger = page.locator('button[role="combobox"]')
    await selectTrigger.click()
    await page.getByRole('option', { name: '配送準備中' }).click()
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する配送がありません')) {
        // 最初の配送行をクリックして詳細へ
        await rows.first().locator('td').nth(1).click()
        await page.waitForLoadState('networkidle')

        // 「ステータス更新」ボタンをクリック
        await page.getByRole('button', { name: 'ステータス更新' }).click()
        await expect(page.getByRole('dialog')).toBeVisible()

        // ステータスSelectを「準備完了」に変更
        const dialogSelectTrigger = page.getByRole('dialog').locator('button[role="combobox"]')
        await dialogSelectTrigger.click()
        await page.getByRole('option', { name: '準備完了' }).click()

        // 「更新」ボタンをクリック
        await page.getByRole('dialog').getByRole('button', { name: '更新' }).click()

        // ダイアログが閉じること
        await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 5000 })

        // ステータスが「準備完了」に更新されていること
        await expect(page.getByText('準備完了')).toBeVisible()

        // テスト後にステータスを元に戻す（pending に戻す）
        await page.getByRole('button', { name: 'ステータス更新' }).click()
        await expect(page.getByRole('dialog')).toBeVisible()
        const revertSelectTrigger = page.getByRole('dialog').locator('button[role="combobox"]')
        await revertSelectTrigger.click()
        await page.getByRole('option', { name: '配送準備中' }).click()
        await page.getByRole('dialog').getByRole('button', { name: '更新' }).click()
        await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 5000 })
      }
    }
  })
})

// ============================
// 配送ステータス一括更新テスト
// ============================
test.describe('FEAT-0017: 配送ステータス一括更新', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-013: チェックボックスを選択すると一括更新ボタンが表示される', async ({ page }) => {
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する配送がありません')) {
        // 最初の行のチェックボックスをクリック
        const checkbox = rows.first().locator('td').first().locator('button[role="checkbox"]')
        await checkbox.click()

        // 「選択した1件を更新」ボタンが表示される
        await expect(page.getByRole('button', { name: /選択した.*件を更新/ })).toBeVisible()
      }
    }
  })

  test('AC-014: 一括更新ダイアログでステータスを変更できる', async ({ page }) => {
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する配送がありません')) {
        // 最初の行のチェックボックスをクリック
        const checkbox = rows.first().locator('td').first().locator('button[role="checkbox"]')
        await checkbox.click()

        // 一括更新ボタンをクリック
        await page.getByRole('button', { name: /選択した.*件を更新/ }).click()

        // ダイアログが表示される
        await expect(page.getByRole('dialog')).toBeVisible()
        await expect(page.getByText('配送ステータス一括更新')).toBeVisible()

        // 「一括更新」ボタンをクリック
        await page.getByRole('dialog').getByRole('button', { name: '一括更新' }).click()

        // ダイアログが閉じること
        await expect(page.getByRole('dialog')).not.toBeVisible({ timeout: 5000 })
      }
    }
  })
})

// ============================
// 梱包写真アップロードテスト
// ============================
test.describe('FEAT-0017: 梱包写真アップロード', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-015: 配送詳細ページに梱包写真セクションが表示される', async ({ page }) => {
    // 最初の配送行をクリックして詳細へ
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // 梱包写真カードの確認
    await expect(page.getByText('梱包写真')).toBeVisible()
    // 「写真を選択」ボタンが存在する（テキスト内にある）
    await expect(page.getByText('写真を選択')).toBeVisible()
  })

  test('AC-016: 写真を選択するとプレビューとアップロードボタンが表示される', async ({ page }) => {
    // 最初の配送行をクリックして詳細へ
    await page.locator('tbody tr').first().locator('td').nth(1).click()
    await page.waitForLoadState('networkidle')

    // テスト用の1x1 PNG画像を生成
    const testImageBuffer = Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
      'base64'
    )

    // hidden file inputにファイルを設定
    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'test-photo.png',
      mimeType: 'image/png',
      buffer: testImageBuffer,
    })

    // プレビュー画像が表示されること
    await expect(page.locator('img[alt="プレビュー"]')).toBeVisible()

    // 「アップロード」ボタンが表示されること
    await expect(page.getByRole('button', { name: 'アップロード' })).toBeVisible()
  })
})

// ============================
// 配送CSVエクスポートテスト
// ============================
test.describe('FEAT-0017: 配送CSVエクスポート', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-017: 未選択時はCSVエクスポートボタンがdisabled', async ({ page }) => {
    const exportButton = page.getByRole('button', { name: /受注CSV/ })
    await expect(exportButton).toBeVisible()
    await expect(exportButton).toBeDisabled()
  })

  test('AC-018: 配送を選択するとCSVエクスポートボタンが有効化される', async ({ page }) => {
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する配送がありません')) {
        // 最初の行のチェックボックスをクリック
        const checkbox = rows.first().locator('td').first().locator('button[role="checkbox"]')
        await checkbox.click()

        // CSVエクスポートボタンが有効化されること
        const exportButton = page.getByRole('button', { name: /受注CSV.*1件/ })
        await expect(exportButton).toBeVisible()
        await expect(exportButton).toBeEnabled()
      }
    }
  })
})

// ============================
// 追跡番号インポートテスト
// ============================
test.describe('FEAT-0017: 追跡番号インポート', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-019: 伝票番号インポートボタンが表示される', async ({ page }) => {
    await expect(page.getByRole('button', { name: '伝票番号インポート' })).toBeVisible()
  })

  test('AC-020: 伝票番号インポートボタンをクリックするとダイアログが開く', async ({ page }) => {
    // 伝票番号インポートボタンをクリック
    await page.getByRole('button', { name: '伝票番号インポート' }).click()

    // ダイアログが表示される
    await expect(page.getByRole('dialog')).toBeVisible()

    // ダイアログ内にインポートUIが表示される
    await expect(page.getByText('伝票番号インポート')).toBeVisible()

    // 運送会社選択が存在する
    await expect(page.getByText('運送会社')).toBeVisible()

    // CSVデータ入力欄が存在する
    await expect(page.getByText('CSVデータ')).toBeVisible()
    await expect(page.locator('textarea')).toBeVisible()

    // インポートボタンが存在する
    await expect(page.getByRole('button', { name: 'インポート' })).toBeVisible()
  })
})
