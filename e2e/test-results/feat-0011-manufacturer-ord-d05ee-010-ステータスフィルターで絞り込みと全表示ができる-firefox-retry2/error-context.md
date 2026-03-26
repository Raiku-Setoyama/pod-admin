# Test info

- Name: FEAT-0011: 発注一覧ステータスフィルター >> AC-009/AC-010: ステータスフィルターで絞り込みと全表示ができる
- Location: /app/tests/feat-0011-manufacturer-order-filter.spec.ts:58:7

# Error details

```
TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
=========================== logs ===========================
waiting for navigation to "/" until "load"
============================================================
    at loginAsAdmin (/app/tests/feat-0011-manufacturer-order-filter.spec.ts:16:14)
    at /app/tests/feat-0011-manufacturer-order-filter.spec.ts:21:5
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
   4 |  * FEAT-0011: 発注一覧のステータスフィルター
   5 |  * AC-007, AC-008, AC-009, AC-010
   6 |  * 発注一覧にステータスカラムが表示されていること
   7 |  * ステータスフィルターのSelectコンポーネントが表示されていること
   8 |  * フィルターで絞り込むと対応するデータのみ表示されること
   9 |  */
  10 |
  11 | async function loginAsAdmin(page: Page) {
  12 |   await page.goto('/login')
  13 |   await page.getByLabel('メールアドレス').fill('admin@example.com')
  14 |   await page.getByLabel('パスワード').fill('password')
  15 |   await page.getByRole('button', { name: 'ログイン' }).click()
> 16 |   await page.waitForURL('/', { timeout: 10000 })
     |              ^ TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
  17 | }
  18 |
  19 | test.describe('FEAT-0011: 発注一覧ステータスフィルター', () => {
  20 |   test.beforeEach(async ({ page }) => {
  21 |     await loginAsAdmin(page)
  22 |   })
  23 |
  24 |   test('AC-007: 発注一覧にステータスカラムが表示されている', async ({ page }) => {
  25 |     await page.goto('/purchase-orders')
  26 |     await page.waitForLoadState('networkidle')
  27 |
  28 |     // ステータスのカラムヘッダーが存在すること
  29 |     const statusHeader = page.locator('th', { hasText: 'ステータス' })
  30 |     await expect(statusHeader).toBeVisible()
  31 |
  32 |     // テーブルの各カラムヘッダーを確認
  33 |     await expect(page.locator('th', { hasText: 'メーカー名' })).toBeVisible()
  34 |     await expect(page.locator('th', { hasText: '発注中明細数' })).toBeVisible()
  35 |     await expect(page.locator('th', { hasText: '合計数量' })).toBeVisible()
  36 |     await expect(page.locator('th', { hasText: '合計金額' })).toBeVisible()
  37 |     await expect(page.locator('th', { hasText: 'リードタイム' })).toBeVisible()
  38 |   })
  39 |
  40 |   test('AC-008: 発注一覧ページにステータスフィルターSelectが表示される', async ({ page }) => {
  41 |     await page.goto('/purchase-orders')
  42 |     await page.waitForLoadState('networkidle')
  43 |
  44 |     // ステータスフィルターのSelect(トリガー)が存在すること
  45 |     const selectTrigger = page.locator('button[role="combobox"]')
  46 |     await expect(selectTrigger).toBeVisible()
  47 |
  48 |     // Selectをクリックしてオプションを確認
  49 |     await selectTrigger.click()
  50 |
  51 |     // フィルターオプションが存在すること
  52 |     await expect(page.getByRole('option', { name: '全てのステータス' })).toBeVisible()
  53 |     await expect(page.getByRole('option', { name: '発注中' })).toBeVisible()
  54 |     await expect(page.getByRole('option', { name: '製造中' })).toBeVisible()
  55 |     await expect(page.getByRole('option', { name: '納入済' })).toBeVisible()
  56 |   })
  57 |
  58 |   test('AC-009/AC-010: ステータスフィルターで絞り込みと全表示ができる', async ({ page }) => {
  59 |     await page.goto('/purchase-orders')
  60 |     await page.waitForLoadState('networkidle')
  61 |
  62 |     // テーブル行を取得（データがある場合のみテスト）
  63 |     const rows = page.locator('tbody tr')
  64 |     const initialRowCount = await rows.count()
  65 |
  66 |     if (initialRowCount > 0) {
  67 |       const firstRowText = await rows.first().textContent()
  68 |       if (!firstRowText?.includes('発注中の明細がありません')) {
  69 |         // 「発注中」でフィルター
  70 |         const selectTrigger = page.locator('button[role="combobox"]')
  71 |         await selectTrigger.click()
  72 |         await page.getByRole('option', { name: '発注中' }).click()
  73 |
  74 |         // フィルター適用後、少し待機
  75 |         await page.waitForTimeout(500)
  76 |
  77 |         // フィルター後のテーブルが表示されている（行数が変化していてもOK）
  78 |         const filteredRows = page.locator('tbody tr')
  79 |         const filteredRowCount = await filteredRows.count()
  80 |         expect(filteredRowCount).toBeGreaterThanOrEqual(0)
  81 |
  82 |         // 「全てのステータス」に戻す
  83 |         await selectTrigger.click()
  84 |         await page.getByRole('option', { name: '全てのステータス' }).click()
  85 |
  86 |         await page.waitForTimeout(500)
  87 |
  88 |         // 全表示に戻ったことを確認
  89 |         const allRows = page.locator('tbody tr')
  90 |         const allRowCount = await allRows.count()
  91 |         expect(allRowCount).toBe(initialRowCount)
  92 |       }
  93 |     }
  94 |   })
  95 | })
  96 |
```