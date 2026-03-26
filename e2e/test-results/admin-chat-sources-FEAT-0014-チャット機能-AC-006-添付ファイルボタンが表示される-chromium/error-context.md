# Test info

- Name: FEAT-0014: チャット機能 >> AC-006: 添付ファイルボタンが表示される
- Location: /app/tests/admin-chat-sources.spec.ts:103:7

# Error details

```
TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
=========================== logs ===========================
waiting for navigation to "/" until "load"
============================================================
    at loginAsAdmin (/app/tests/admin-chat-sources.spec.ts:19:14)
    at /app/tests/admin-chat-sources.spec.ts:27:5
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
   4 |  * FEAT-0014: チャット・受注元管理 E2Eテスト
   5 |  *
   6 |  * 対象機能:
   7 |  * - チャットメッセージ一覧取得
   8 |  * - チャットメッセージ送信（添付ファイル対応）
   9 |  * - チャット一覧取得
   10 |  * - 添付ファイルダウンロード
   11 |  * - 受注元登録・管理
   12 |  */
   13 |
   14 | async function loginAsAdmin(page: Page) {
   15 |   await page.goto('/login')
   16 |   await page.getByLabel('メールアドレス').fill('admin@example.com')
   17 |   await page.getByLabel('パスワード').fill('password')
   18 |   await page.getByRole('button', { name: 'ログイン' }).click()
>  19 |   await page.waitForURL('/', { timeout: 10000 })
      |              ^ TimeoutError: page.waitForURL: Timeout 10000ms exceeded.
   20 | }
   21 |
   22 | // ============================================================
   23 | // チャット機能テスト
   24 | // ============================================================
   25 | test.describe('FEAT-0014: チャット機能', () => {
   26 |   test.beforeEach(async ({ page }) => {
   27 |     await loginAsAdmin(page)
   28 |   })
   29 |
   30 |   test('AC-001: チャットページにメーカー一覧パネルが表示される', async ({ page }) => {
   31 |     await page.goto('/chat')
   32 |     await page.waitForLoadState('networkidle')
   33 |
   34 |     // メーカー一覧ヘッダーが表示される
   35 |     await expect(page.locator('text=メーカー一覧')).toBeVisible()
   36 |
   37 |     // シードデータのメーカー名が表示される
   38 |     await expect(page.locator('text=シードット')).toBeVisible()
   39 |   })
   40 |
   41 |   test('AC-002: メーカーを選択するとチャットパネルが表示される', async ({ page }) => {
   42 |     await page.goto('/chat')
   43 |     await page.waitForLoadState('networkidle')
   44 |
   45 |     // メーカーを選択
   46 |     await page.locator('text=シードット').click()
   47 |     await page.waitForLoadState('networkidle')
   48 |
   49 |     // チャットヘッダーにメーカー名が表示される
   50 |     const chatHeader = page.locator('h3', { hasText: 'シードット' })
   51 |     await expect(chatHeader).toBeVisible()
   52 |
   53 |     // メッセージ入力欄が表示される
   54 |     await expect(page.getByPlaceholder('メッセージを入力...')).toBeVisible()
   55 |   })
   56 |
   57 |   test('AC-003: メッセージが無い場合、空メッセージが表示される', async ({ page }) => {
   58 |     await page.goto('/chat')
   59 |     await page.waitForLoadState('networkidle')
   60 |
   61 |     // メーカーを選択（メッセージが無い想定）
   62 |     await page.locator('text=シードット').click()
   63 |     await page.waitForLoadState('networkidle')
   64 |
   65 |     // 「メッセージはありません」が表示される
   66 |     await expect(page.locator('text=メッセージはありません')).toBeVisible()
   67 |   })
   68 |
   69 |   test('AC-004: テキストメッセージを送信すると画面に反映される', async ({ page }) => {
   70 |     await page.goto('/chat')
   71 |     await page.waitForLoadState('networkidle')
   72 |
   73 |     // メーカーを選択
   74 |     await page.locator('text=シードット').click()
   75 |     await page.waitForLoadState('networkidle')
   76 |
   77 |     const testMessage = `E2Eテストメッセージ ${Date.now()}`
   78 |
   79 |     // メッセージを入力
   80 |     await page.getByPlaceholder('メッセージを入力...').fill(testMessage)
   81 |
   82 |     // 送信ボタンをクリック
   83 |     const sendButton = page.locator('button').filter({ has: page.locator('svg.lucide-send') })
   84 |     await sendButton.click()
   85 |
   86 |     // 送信したメッセージが表示される
   87 |     await expect(page.locator(`text=${testMessage}`)).toBeVisible({ timeout: 10000 })
   88 |   })
   89 |
   90 |   test('AC-005: 空メッセージは送信できない', async ({ page }) => {
   91 |     await page.goto('/chat')
   92 |     await page.waitForLoadState('networkidle')
   93 |
   94 |     // メーカーを選択
   95 |     await page.locator('text=シードット').click()
   96 |     await page.waitForLoadState('networkidle')
   97 |
   98 |     // メッセージ入力欄が空の状態で送信ボタンが無効であること
   99 |     const sendButton = page.locator('button').filter({ has: page.locator('svg.lucide-send') })
  100 |     await expect(sendButton).toBeDisabled()
  101 |   })
  102 |
  103 |   test('AC-006: 添付ファイルボタンが表示される', async ({ page }) => {
  104 |     await page.goto('/chat')
  105 |     await page.waitForLoadState('networkidle')
  106 |
  107 |     // メーカーを選択
  108 |     await page.locator('text=シードット').click()
  109 |     await page.waitForLoadState('networkidle')
  110 |
  111 |     // 添付ファイルボタン（クリップアイコン）が表示される
  112 |     const attachButton = page.locator('button').filter({ has: page.locator('svg.lucide-paperclip') })
  113 |     await expect(attachButton).toBeVisible()
  114 |   })
  115 | })
  116 |
  117 | // ============================================================
  118 | // 受注元管理テスト
  119 | // ============================================================
```