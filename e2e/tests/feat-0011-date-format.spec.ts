import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0011: 日付フォーマット確認
 * AC-001, AC-002, AC-003, AC-004
 * 各一覧ページの日付カラムがYYYY/MM/DD HH:MM形式で表示されていること
 */

// YYYY/MM/DD HH:MM 形式の正規表現
const DATE_FORMAT_REGEX = /\d{4}\/\d{2}\/\d{2}\s\d{2}:\d{2}/

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

test.describe('FEAT-0011: 日付フォーマット統一', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-001: 受注一覧の受注日カラムがYYYY/MM/DD HH:MM形式で表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    // 受注日のカラムヘッダーが存在すること
    const header = page.locator('th', { hasText: '受注日' })
    await expect(header).toBeVisible()

    // テーブル行が存在する場合、日付フォーマットを検証
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      // 最初の行が「該当する受注がありません」でないことを確認
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        // 受注日カラム（7番目のtd、0-indexed で6）の日付フォーマットを確認
        const dateCell = rows.first().locator('td').nth(6)
        const dateText = await dateCell.textContent()
        expect(dateText?.trim()).toMatch(DATE_FORMAT_REGEX)
      }
    }
  })

  test('AC-002: 配送一覧の作成日カラムがYYYY/MM/DD HH:MM形式で表示される', async ({ page }) => {
    await page.goto('/shipments')
    await page.waitForLoadState('networkidle')

    // 作成日のカラムヘッダーが存在すること
    const header = page.locator('th', { hasText: '作成日' })
    await expect(header).toBeVisible()

    // テーブル行が存在する場合、日付フォーマットを検証
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する配送がありません')) {
        // 作成日カラム（6番目のtd、0-indexed で5）の日付フォーマットを確認
        const dateCell = rows.first().locator('td').nth(5)
        const dateText = await dateCell.textContent()
        expect(dateText?.trim()).toMatch(DATE_FORMAT_REGEX)
      }
    }
  })

  test('AC-003: 発注詳細の受注日カラムがYYYY/MM/DD HH:MM形式で表示される', async ({ page }) => {
    await page.goto('/purchase-orders')
    await page.waitForLoadState('networkidle')

    // 発注一覧にデータがあれば最初の行をクリックして詳細へ遷移
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('発注中の明細がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 発注詳細ページの受注日カラムヘッダーが存在すること
        const header = page.locator('th', { hasText: '受注日' })
        await expect(header).toBeVisible()

        // 明細テーブルの行を取得
        const detailRows = page.locator('tbody tr')
        const detailRowCount = await detailRows.count()

        if (detailRowCount > 0) {
          const detailFirstRowText = await detailRows.first().textContent()
          if (!detailFirstRowText?.includes('発注中の明細がありません')) {
            // 受注日カラム（9番目のtd、0-indexed で8）の日付フォーマットを確認
            const dateCell = detailRows.first().locator('td').nth(8)
            const dateText = await dateCell.textContent()
            expect(dateText?.trim()).toMatch(DATE_FORMAT_REGEX)
          }
        }
      }
    }
  })
})
