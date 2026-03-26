# Test info

- Name: FEAT-0011: 日付フォーマット統一 >> AC-003: 発注詳細の受注日カラムがYYYY/MM/DD HH:MM形式で表示される
- Location: /app/tests/feat-0011-date-format.spec.ts:72:7

# Error details

```
TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
=========================== logs ===========================
waiting for navigation to "/" until "load"
============================================================
    at loginAsAdmin (/app/tests/feat-0011-date-format.spec.ts:17:14)
    at /app/tests/feat-0011-date-format.spec.ts:22:5
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
   4 |  * FEAT-0011: 日付フォーマット確認
   5 |  * AC-001, AC-002, AC-003, AC-004
   6 |  * 各一覧ページの日付カラムがYYYY/MM/DD HH:MM形式で表示されていること
   7 |  */
   8 |
   9 | // YYYY/MM/DD HH:MM 形式の正規表現
   10 | const DATE_FORMAT_REGEX = /\d{4}\/\d{2}\/\d{2}\s\d{2}:\d{2}/
   11 |
   12 | async function loginAsAdmin(page: Page) {
   13 |   await page.goto('/login')
   14 |   await page.getByLabel('メールアドレス').fill('admin@example.com')
   15 |   await page.getByLabel('パスワード').fill('password')
   16 |   await page.getByRole('button', { name: 'ログイン' }).click()
>  17 |   await page.waitForURL('/', { timeout: 10000 })
      |              ^ TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
   18 | }
   19 |
   20 | test.describe('FEAT-0011: 日付フォーマット統一', () => {
   21 |   test.beforeEach(async ({ page }) => {
   22 |     await loginAsAdmin(page)
   23 |   })
   24 |
   25 |   test('AC-001: 受注一覧の受注日カラムがYYYY/MM/DD HH:MM形式で表示される', async ({ page }) => {
   26 |     await page.goto('/orders')
   27 |     await page.waitForLoadState('networkidle')
   28 |
   29 |     // 受注日のカラムヘッダーが存在すること
   30 |     const header = page.locator('th', { hasText: '受注日' })
   31 |     await expect(header).toBeVisible()
   32 |
   33 |     // テーブル行が存在する場合、日付フォーマットを検証
   34 |     const rows = page.locator('tbody tr')
   35 |     const rowCount = await rows.count()
   36 |
   37 |     if (rowCount > 0) {
   38 |       // 最初の行が「該当する受注がありません」でないことを確認
   39 |       const firstRowText = await rows.first().textContent()
   40 |       if (!firstRowText?.includes('該当する受注がありません')) {
   41 |         // 受注日カラム（7番目のtd、0-indexed で6）の日付フォーマットを確認
   42 |         const dateCell = rows.first().locator('td').nth(6)
   43 |         const dateText = await dateCell.textContent()
   44 |         expect(dateText?.trim()).toMatch(DATE_FORMAT_REGEX)
   45 |       }
   46 |     }
   47 |   })
   48 |
   49 |   test('AC-002: 配送一覧の作成日カラムがYYYY/MM/DD HH:MM形式で表示される', async ({ page }) => {
   50 |     await page.goto('/shipments')
   51 |     await page.waitForLoadState('networkidle')
   52 |
   53 |     // 作成日のカラムヘッダーが存在すること
   54 |     const header = page.locator('th', { hasText: '作成日' })
   55 |     await expect(header).toBeVisible()
   56 |
   57 |     // テーブル行が存在する場合、日付フォーマットを検証
   58 |     const rows = page.locator('tbody tr')
   59 |     const rowCount = await rows.count()
   60 |
   61 |     if (rowCount > 0) {
   62 |       const firstRowText = await rows.first().textContent()
   63 |       if (!firstRowText?.includes('該当する配送がありません')) {
   64 |         // 作成日カラム（6番目のtd、0-indexed で5）の日付フォーマットを確認
   65 |         const dateCell = rows.first().locator('td').nth(5)
   66 |         const dateText = await dateCell.textContent()
   67 |         expect(dateText?.trim()).toMatch(DATE_FORMAT_REGEX)
   68 |       }
   69 |     }
   70 |   })
   71 |
   72 |   test('AC-003: 発注詳細の受注日カラムがYYYY/MM/DD HH:MM形式で表示される', async ({ page }) => {
   73 |     await page.goto('/purchase-orders')
   74 |     await page.waitForLoadState('networkidle')
   75 |
   76 |     // 発注一覧にデータがあれば最初の行をクリックして詳細へ遷移
   77 |     const rows = page.locator('tbody tr')
   78 |     const rowCount = await rows.count()
   79 |
   80 |     if (rowCount > 0) {
   81 |       const firstRowText = await rows.first().textContent()
   82 |       if (!firstRowText?.includes('発注中の明細がありません')) {
   83 |         await rows.first().click()
   84 |         await page.waitForLoadState('networkidle')
   85 |
   86 |         // 発注詳細ページの受注日カラムヘッダーが存在すること
   87 |         const header = page.locator('th', { hasText: '受注日' })
   88 |         await expect(header).toBeVisible()
   89 |
   90 |         // 明細テーブルの行を取得
   91 |         const detailRows = page.locator('tbody tr')
   92 |         const detailRowCount = await detailRows.count()
   93 |
   94 |         if (detailRowCount > 0) {
   95 |           const detailFirstRowText = await detailRows.first().textContent()
   96 |           if (!detailFirstRowText?.includes('発注中の明細がありません')) {
   97 |             // 受注日カラム（9番目のtd、0-indexed で8）の日付フォーマットを確認
   98 |             const dateCell = detailRows.first().locator('td').nth(8)
   99 |             const dateText = await dateCell.textContent()
  100 |             expect(dateText?.trim()).toMatch(DATE_FORMAT_REGEX)
  101 |           }
  102 |         }
  103 |       }
  104 |     }
  105 |   })
  106 | })
  107 |
```