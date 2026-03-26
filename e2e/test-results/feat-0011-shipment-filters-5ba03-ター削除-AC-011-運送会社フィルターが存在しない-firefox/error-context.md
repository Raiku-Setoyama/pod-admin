# Test info

- Name: FEAT-0011: 配送一覧フィルター削除 >> AC-011: 運送会社フィルターが存在しない
- Location: /app/tests/feat-0011-shipment-filters.spec.ts:24:7

# Error details

```
TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
=========================== logs ===========================
waiting for navigation to "/" until "load"
============================================================
    at loginAsAdmin (/app/tests/feat-0011-shipment-filters.spec.ts:14:14)
    at /app/tests/feat-0011-shipment-filters.spec.ts:19:5
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
   4 |  * FEAT-0011: 配送一覧フィルター削除確認
   5 |  * AC-011 ~ AC-017
   6 |  * 不要フィルターが削除され、汎用検索欄とステータスフィルターが維持されていること
   7 |  */
   8 |
   9 | async function loginAsAdmin(page: Page) {
  10 |   await page.goto('/login')
  11 |   await page.getByLabel('メールアドレス').fill('admin@example.com')
  12 |   await page.getByLabel('パスワード').fill('password')
  13 |   await page.getByRole('button', { name: 'ログイン' }).click()
> 14 |   await page.waitForURL('/', { timeout: 10000 })
     |              ^ TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
  15 | }
  16 |
  17 | test.describe('FEAT-0011: 配送一覧フィルター削除', () => {
  18 |   test.beforeEach(async ({ page }) => {
  19 |     await loginAsAdmin(page)
  20 |     await page.goto('/shipments')
  21 |     await page.waitForLoadState('networkidle')
  22 |   })
  23 |
  24 |   test('AC-011: 運送会社フィルターが存在しない', async ({ page }) => {
  25 |     // 運送会社に関するSelectやInputが存在しないこと
  26 |     await expect(page.getByPlaceholder(/運送会社/)).not.toBeVisible()
  27 |     await expect(page.locator('text=運送会社').first()).not.toBeVisible()
  28 |   })
  29 |
  30 |   test('AC-012: 作成日時ソートが存在しない', async ({ page }) => {
  31 |     // 並び替え/ソートに関するUI要素が存在しないこと
  32 |     await expect(page.getByText('並び替え')).not.toBeVisible()
  33 |     await expect(page.getByText('ソート')).not.toBeVisible()
  34 |     await expect(page.getByText('作成日時順')).not.toBeVisible()
  35 |   })
  36 |
  37 |   test('AC-013: 伝票番号検索欄が存在しない', async ({ page }) => {
  38 |     // 伝票番号専用の検索入力欄が存在しないこと
  39 |     // （汎用検索欄のプレースホルダーには「伝票番号」が含まれるが、専用の入力欄は削除済み）
  40 |     const trackingInputs = page.locator('input[placeholder*="伝票番号で検索"]')
  41 |     // 汎用検索欄のプレースホルダーは「配送ID、伝票番号、顧客名で検索...」なので除外
  42 |     const dedicatedTrackingInput = page.locator('input[placeholder="伝票番号"]')
  43 |     await expect(dedicatedTrackingInput).not.toBeVisible()
  44 |   })
  45 |
  46 |   test('AC-014: 発送日時フィルターが存在しない', async ({ page }) => {
  47 |     // 発送日時に関する日付入力が存在しないこと
  48 |     await expect(page.getByText('発送日時')).not.toBeVisible()
  49 |     await expect(page.getByText('発送日')).not.toBeVisible()
  50 |     // 日付範囲入力（type="date"）が発送用として存在しないこと
  51 |     const dateInputs = page.locator('input[type="date"]')
  52 |     const dateCount = await dateInputs.count()
  53 |     // 配送フィルターには日付入力は含まれない
  54 |     expect(dateCount).toBe(0)
  55 |   })
  56 |
  57 |   test('AC-015: 配送完了予定日時フィルターが存在しない', async ({ page }) => {
  58 |     // 配送完了予定日時に関するUI要素が存在しないこと
  59 |     await expect(page.getByText('配送完了予定')).not.toBeVisible()
  60 |     await expect(page.getByText('配達予定')).not.toBeVisible()
  61 |   })
  62 |
  63 |   test('AC-016: 汎用検索欄とステータスフィルターは維持されている', async ({ page }) => {
  64 |     // 汎用検索入力欄が存在すること
  65 |     const searchInput = page.getByPlaceholder('配送ID、伝票番号、顧客名で検索...')
  66 |     await expect(searchInput).toBeVisible()
  67 |
  68 |     // ステータスフィルターのSelectが存在すること
  69 |     const selectTrigger = page.locator('button[role="combobox"]')
  70 |     await expect(selectTrigger).toBeVisible()
  71 |
  72 |     // Selectをクリックしてステータスオプションを確認
  73 |     await selectTrigger.click()
  74 |     await expect(page.getByRole('option', { name: '全てのステータス' })).toBeVisible()
  75 |     await expect(page.getByRole('option', { name: '配送準備中' })).toBeVisible()
  76 |     await expect(page.getByRole('option', { name: '準備完了' })).toBeVisible()
  77 |     await expect(page.getByRole('option', { name: '発送完了' })).toBeVisible()
  78 |   })
  79 |
  80 |   test('AC-017: フィルタリセットボタンが正常に動作する', async ({ page }) => {
  81 |     // 検索欄に値を入力
  82 |     const searchInput = page.getByPlaceholder('配送ID、伝票番号、顧客名で検索...')
  83 |     await searchInput.fill('テスト検索')
  84 |
  85 |     // フィルタをリセットボタンが表示されること
  86 |     const resetButton = page.getByRole('button', { name: 'フィルタをリセット' })
  87 |     await expect(resetButton).toBeVisible()
  88 |
  89 |     // リセットボタンをクリック
  90 |     await resetButton.click()
  91 |
  92 |     // 検索欄がクリアされていること
  93 |     await expect(searchInput).toHaveValue('')
  94 |
  95 |     // リセットボタンが非表示になること（アクティブなフィルターがないため）
  96 |     await expect(resetButton).not.toBeVisible()
  97 |   })
  98 | })
  99 |
```