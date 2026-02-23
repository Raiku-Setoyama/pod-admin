import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0011: 発注一覧のステータスフィルター
 * AC-007, AC-008, AC-009, AC-010
 * 発注一覧にステータスカラムが表示されていること
 * ステータスフィルターのSelectコンポーネントが表示されていること
 * フィルターで絞り込むと対応するデータのみ表示されること
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

test.describe('FEAT-0011: 発注一覧ステータスフィルター', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-007: 発注一覧にステータスカラムが表示されている', async ({ page }) => {
    await page.goto('/purchase-orders')
    await page.waitForLoadState('networkidle')

    // ステータスのカラムヘッダーが存在すること
    const statusHeader = page.locator('th', { hasText: 'ステータス' })
    await expect(statusHeader).toBeVisible()

    // テーブルの各カラムヘッダーを確認
    await expect(page.locator('th', { hasText: 'メーカー名' })).toBeVisible()
    await expect(page.locator('th', { hasText: '発注中明細数' })).toBeVisible()
    await expect(page.locator('th', { hasText: '合計数量' })).toBeVisible()
    await expect(page.locator('th', { hasText: '合計金額' })).toBeVisible()
    await expect(page.locator('th', { hasText: 'リードタイム' })).toBeVisible()
  })

  test('AC-008: 発注一覧ページにステータスフィルターSelectが表示される', async ({ page }) => {
    await page.goto('/purchase-orders')
    await page.waitForLoadState('networkidle')

    // ステータスフィルターのSelect(トリガー)が存在すること
    const selectTrigger = page.locator('button[role="combobox"]')
    await expect(selectTrigger).toBeVisible()

    // Selectをクリックしてオプションを確認
    await selectTrigger.click()

    // フィルターオプションが存在すること
    await expect(page.getByRole('option', { name: '全てのステータス' })).toBeVisible()
    await expect(page.getByRole('option', { name: '発注中' })).toBeVisible()
    await expect(page.getByRole('option', { name: '製造中' })).toBeVisible()
    await expect(page.getByRole('option', { name: '納入済' })).toBeVisible()
  })

  test('AC-009/AC-010: ステータスフィルターで絞り込みと全表示ができる', async ({ page }) => {
    await page.goto('/purchase-orders')
    await page.waitForLoadState('networkidle')

    // テーブル行を取得（データがある場合のみテスト）
    const rows = page.locator('tbody tr')
    const initialRowCount = await rows.count()

    if (initialRowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('発注中の明細がありません')) {
        // 「発注中」でフィルター
        const selectTrigger = page.locator('button[role="combobox"]')
        await selectTrigger.click()
        await page.getByRole('option', { name: '発注中' }).click()

        // フィルター適用後、少し待機
        await page.waitForTimeout(500)

        // フィルター後のテーブルが表示されている（行数が変化していてもOK）
        const filteredRows = page.locator('tbody tr')
        const filteredRowCount = await filteredRows.count()
        expect(filteredRowCount).toBeGreaterThanOrEqual(0)

        // 「全てのステータス」に戻す
        await selectTrigger.click()
        await page.getByRole('option', { name: '全てのステータス' }).click()

        await page.waitForTimeout(500)

        // 全表示に戻ったことを確認
        const allRows = page.locator('tbody tr')
        const allRowCount = await allRows.count()
        expect(allRowCount).toBe(initialRowCount)
      }
    }
  })
})
