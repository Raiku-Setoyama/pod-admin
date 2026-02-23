import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0011: 配送一覧フィルター削除確認
 * AC-011 ~ AC-017
 * 不要フィルターが削除され、汎用検索欄とステータスフィルターが維持されていること
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

test.describe('FEAT-0011: 配送一覧フィルター削除', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')
  })

  test('AC-011: 運送会社フィルターが存在しない', async ({ page }) => {
    // 運送会社に関するSelectやInputが存在しないこと
    await expect(page.getByPlaceholder(/運送会社/)).not.toBeVisible()
    await expect(page.locator('text=運送会社').first()).not.toBeVisible()
  })

  test('AC-012: 作成日時ソートが存在しない', async ({ page }) => {
    // 並び替え/ソートに関するUI要素が存在しないこと
    await expect(page.getByText('並び替え')).not.toBeVisible()
    await expect(page.getByText('ソート')).not.toBeVisible()
    await expect(page.getByText('作成日時順')).not.toBeVisible()
  })

  test('AC-013: 伝票番号検索欄が存在しない', async ({ page }) => {
    // 伝票番号専用の検索入力欄が存在しないこと
    // （汎用検索欄のプレースホルダーには「伝票番号」が含まれるが、専用の入力欄は削除済み）
    const trackingInputs = page.locator('input[placeholder*="伝票番号で検索"]')
    // 汎用検索欄のプレースホルダーは「配送ID、伝票番号、顧客名で検索...」なので除外
    const dedicatedTrackingInput = page.locator('input[placeholder="伝票番号"]')
    await expect(dedicatedTrackingInput).not.toBeVisible()
  })

  test('AC-014: 発送日時フィルターが存在しない', async ({ page }) => {
    // 発送日時に関する日付入力が存在しないこと
    await expect(page.getByText('発送日時')).not.toBeVisible()
    await expect(page.getByText('発送日')).not.toBeVisible()
    // 日付範囲入力（type="date"）が発送用として存在しないこと
    const dateInputs = page.locator('input[type="date"]')
    const dateCount = await dateInputs.count()
    // 配送フィルターには日付入力は含まれない
    expect(dateCount).toBe(0)
  })

  test('AC-015: 配送完了予定日時フィルターが存在しない', async ({ page }) => {
    // 配送完了予定日時に関するUI要素が存在しないこと
    await expect(page.getByText('配送完了予定')).not.toBeVisible()
    await expect(page.getByText('配達予定')).not.toBeVisible()
  })

  test('AC-016: 汎用検索欄とステータスフィルターは維持されている', async ({ page }) => {
    // 汎用検索入力欄が存在すること
    const searchInput = page.getByPlaceholder('配送ID、伝票番号、顧客名で検索...')
    await expect(searchInput).toBeVisible()

    // ステータスフィルターのSelectが存在すること
    const selectTrigger = page.locator('button[role="combobox"]')
    await expect(selectTrigger).toBeVisible()

    // Selectをクリックしてステータスオプションを確認
    await selectTrigger.click()
    await expect(page.getByRole('option', { name: '全てのステータス' })).toBeVisible()
    await expect(page.getByRole('option', { name: '配送準備中' })).toBeVisible()
    await expect(page.getByRole('option', { name: '準備完了' })).toBeVisible()
    await expect(page.getByRole('option', { name: '発送完了' })).toBeVisible()
  })

  test('AC-017: フィルタリセットボタンが正常に動作する', async ({ page }) => {
    // 検索欄に値を入力
    const searchInput = page.getByPlaceholder('配送ID、伝票番号、顧客名で検索...')
    await searchInput.fill('テスト検索')

    // フィルタをリセットボタンが表示されること
    const resetButton = page.getByRole('button', { name: 'フィルタをリセット' })
    await expect(resetButton).toBeVisible()

    // リセットボタンをクリック
    await resetButton.click()

    // 検索欄がクリアされていること
    await expect(searchInput).toHaveValue('')

    // リセットボタンが非表示になること（アクティブなフィルターがないため）
    await expect(resetButton).not.toBeVisible()
  })
})
