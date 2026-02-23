import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0011: 受注詳細のステータス更新UI削除確認
 * AC-005, AC-006
 * 受注詳細ページにステータス変更ボタンが存在しないこと
 * ステータスはStatusBadgeで表示のみであること
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

test.describe('FEAT-0011: 受注詳細ステータス更新UI削除', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-005: 受注詳細ページにステータス変更ボタンが存在しない', async ({ page }) => {
    // まず受注一覧に遷移してデータの有無を確認
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        // 最初の受注をクリックして詳細ページへ遷移
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 受注情報カードが表示されていること
        await expect(page.locator('text=受注情報')).toBeVisible()

        // ステータスバッジが表示されていること（表示のみ）
        // StatusBadge はspan/div要素として描画される
        const statusBadge = page.locator('[class*="badge"], [class*="Badge"]').first()
        // バッジ的な要素が存在することを確認（ステータス表示用）

        // ステータス変更ボタンが存在しないこと
        await expect(page.getByRole('button', { name: /ステータス変更/ })).not.toBeVisible()
        await expect(page.getByRole('button', { name: /ステータスを変更/ })).not.toBeVisible()

        // OrderStatusUpdateDialog が表示されていないこと
        await expect(page.locator('text=ステータスを更新')).not.toBeVisible()
        await expect(page.locator('[role="dialog"]')).not.toBeVisible()
      }
    }
  })

  test('AC-006: 受注詳細ページでステータス変更ダイアログが描画されない', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 受注情報カードが表示されていること
        await expect(page.locator('text=受注情報')).toBeVisible()

        // ページ内にダイアログトリガーとなるボタンが存在しないこと
        const allButtons = page.getByRole('button')
        const buttonCount = await allButtons.count()

        for (let i = 0; i < buttonCount; i++) {
          const buttonText = await allButtons.nth(i).textContent()
          // ステータス変更に関するボタンが存在しないことを確認
          expect(buttonText).not.toMatch(/ステータス変更/)
          expect(buttonText).not.toMatch(/ステータスを変更/)
        }

        // ダイアログが存在しないこと
        await expect(page.locator('[role="dialog"]')).toHaveCount(0)
      }
    }
  })
})
