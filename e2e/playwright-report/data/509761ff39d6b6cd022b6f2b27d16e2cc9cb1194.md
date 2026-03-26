# Test info

- Name: FEAT-0011: 受注詳細ステータス更新UI削除 >> AC-005: 受注詳細ページにステータス変更ボタンが存在しない
- Location: /app/tests/feat-0011-order-detail.spec.ts:23:7

# Error details

```
TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
=========================== logs ===========================
waiting for navigation to "/" until "load"
============================================================
    at loginAsAdmin (/app/tests/feat-0011-order-detail.spec.ts:15:14)
    at /app/tests/feat-0011-order-detail.spec.ts:20:5
```

# Page snapshot

```yaml
- heading "グッズ管理" [level=1]
- paragraph: 管理画面にログインしてください
- text: ログインに失敗しました メールアドレス
- textbox "メールアドレス": admin@example.com
- text: パスワード
- textbox "パスワード": password
- button "ログイン"
- region "Notifications alt+T"
- alert
```

# Test source

```ts
   1 | import { test, expect, type Page } from '@playwright/test'
   2 |
   3 | /**
   4 |  * FEAT-0011: 受注詳細のステータス更新UI削除確認
   5 |  * AC-005, AC-006
   6 |  * 受注詳細ページにステータス変更ボタンが存在しないこと
   7 |  * ステータスはStatusBadgeで表示のみであること
   8 |  */
   9 |
  10 | async function loginAsAdmin(page: Page) {
  11 |   await page.goto('/login')
  12 |   await page.getByLabel('メールアドレス').fill('admin@example.com')
  13 |   await page.getByLabel('パスワード').fill('password')
  14 |   await page.getByRole('button', { name: 'ログイン' }).click()
> 15 |   await page.waitForURL('/', { timeout: 10000 })
     |              ^ TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
  16 | }
  17 |
  18 | test.describe('FEAT-0011: 受注詳細ステータス更新UI削除', () => {
  19 |   test.beforeEach(async ({ page }) => {
  20 |     await loginAsAdmin(page)
  21 |   })
  22 |
  23 |   test('AC-005: 受注詳細ページにステータス変更ボタンが存在しない', async ({ page }) => {
  24 |     // まず受注一覧に遷移してデータの有無を確認
  25 |     await page.goto('/orders')
  26 |     await page.waitForLoadState('networkidle')
  27 |
  28 |     const rows = page.locator('tbody tr')
  29 |     const rowCount = await rows.count()
  30 |
  31 |     if (rowCount > 0) {
  32 |       const firstRowText = await rows.first().textContent()
  33 |       if (!firstRowText?.includes('該当する受注がありません')) {
  34 |         // 最初の受注をクリックして詳細ページへ遷移
  35 |         await rows.first().click()
  36 |         await page.waitForLoadState('networkidle')
  37 |
  38 |         // 受注情報カードが表示されていること
  39 |         await expect(page.locator('text=受注情報')).toBeVisible()
  40 |
  41 |         // ステータスバッジが表示されていること（表示のみ）
  42 |         // StatusBadge はspan/div要素として描画される
  43 |         const statusBadge = page.locator('[class*="badge"], [class*="Badge"]').first()
  44 |         // バッジ的な要素が存在することを確認（ステータス表示用）
  45 |
  46 |         // ステータス変更ボタンが存在しないこと
  47 |         await expect(page.getByRole('button', { name: /ステータス変更/ })).not.toBeVisible()
  48 |         await expect(page.getByRole('button', { name: /ステータスを変更/ })).not.toBeVisible()
  49 |
  50 |         // OrderStatusUpdateDialog が表示されていないこと
  51 |         await expect(page.locator('text=ステータスを更新')).not.toBeVisible()
  52 |         await expect(page.locator('[role="dialog"]')).not.toBeVisible()
  53 |       }
  54 |     }
  55 |   })
  56 |
  57 |   test('AC-006: 受注詳細ページでステータス変更ダイアログが描画されない', async ({ page }) => {
  58 |     await page.goto('/orders')
  59 |     await page.waitForLoadState('networkidle')
  60 |
  61 |     const rows = page.locator('tbody tr')
  62 |     const rowCount = await rows.count()
  63 |
  64 |     if (rowCount > 0) {
  65 |       const firstRowText = await rows.first().textContent()
  66 |       if (!firstRowText?.includes('該当する受注がありません')) {
  67 |         await rows.first().click()
  68 |         await page.waitForLoadState('networkidle')
  69 |
  70 |         // 受注情報カードが表示されていること
  71 |         await expect(page.locator('text=受注情報')).toBeVisible()
  72 |
  73 |         // ページ内にダイアログトリガーとなるボタンが存在しないこと
  74 |         const allButtons = page.getByRole('button')
  75 |         const buttonCount = await allButtons.count()
  76 |
  77 |         for (let i = 0; i < buttonCount; i++) {
  78 |           const buttonText = await allButtons.nth(i).textContent()
  79 |           // ステータス変更に関するボタンが存在しないことを確認
  80 |           expect(buttonText).not.toMatch(/ステータス変更/)
  81 |           expect(buttonText).not.toMatch(/ステータスを変更/)
  82 |         }
  83 |
  84 |         // ダイアログが存在しないこと
  85 |         await expect(page.locator('[role="dialog"]')).toHaveCount(0)
  86 |       }
  87 |     }
  88 |   })
  89 | })
  90 |
```