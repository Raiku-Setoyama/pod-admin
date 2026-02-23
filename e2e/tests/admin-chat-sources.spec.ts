import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0014: チャット・受注元管理 E2Eテスト
 *
 * 対象機能:
 * - チャットメッセージ一覧取得
 * - チャットメッセージ送信（添付ファイル対応）
 * - チャット一覧取得
 * - 添付ファイルダウンロード
 * - 受注元登録・管理
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

// ============================================================
// チャット機能テスト
// ============================================================
test.describe('FEAT-0014: チャット機能', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-001: チャットページにメーカー一覧パネルが表示される', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // メーカー一覧ヘッダーが表示される
    await expect(page.locator('text=メーカー一覧')).toBeVisible()

    // シードデータのメーカー名が表示される
    await expect(page.locator('text=シードット')).toBeVisible()
  })

  test('AC-002: メーカーを選択するとチャットパネルが表示される', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // メーカーを選択
    await page.locator('text=シードット').click()
    await page.waitForLoadState('networkidle')

    // チャットヘッダーにメーカー名が表示される
    const chatHeader = page.locator('h3', { hasText: 'シードット' })
    await expect(chatHeader).toBeVisible()

    // メッセージ入力欄が表示される
    await expect(page.getByPlaceholder('メッセージを入力...')).toBeVisible()
  })

  test('AC-003: メッセージが無い場合、空メッセージが表示される', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // メーカーを選択（メッセージが無い想定）
    await page.locator('text=シードット').click()
    await page.waitForLoadState('networkidle')

    // 「メッセージはありません」が表示される
    await expect(page.locator('text=メッセージはありません')).toBeVisible()
  })

  test('AC-004: テキストメッセージを送信すると画面に反映される', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // メーカーを選択
    await page.locator('text=シードット').click()
    await page.waitForLoadState('networkidle')

    const testMessage = `E2Eテストメッセージ ${Date.now()}`

    // メッセージを入力
    await page.getByPlaceholder('メッセージを入力...').fill(testMessage)

    // 送信ボタンをクリック
    const sendButton = page.locator('button').filter({ has: page.locator('svg.lucide-send') })
    await sendButton.click()

    // 送信したメッセージが表示される
    await expect(page.locator(`text=${testMessage}`)).toBeVisible({ timeout: 10000 })
  })

  test('AC-005: 空メッセージは送信できない', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // メーカーを選択
    await page.locator('text=シードット').click()
    await page.waitForLoadState('networkidle')

    // メッセージ入力欄が空の状態で送信ボタンが無効であること
    const sendButton = page.locator('button').filter({ has: page.locator('svg.lucide-send') })
    await expect(sendButton).toBeDisabled()
  })

  test('AC-006: 添付ファイルボタンが表示される', async ({ page }) => {
    await page.goto('/chat')
    await page.waitForLoadState('networkidle')

    // メーカーを選択
    await page.locator('text=シードット').click()
    await page.waitForLoadState('networkidle')

    // 添付ファイルボタン（クリップアイコン）が表示される
    const attachButton = page.locator('button').filter({ has: page.locator('svg.lucide-paperclip') })
    await expect(attachButton).toBeVisible()
  })
})

// ============================================================
// 受注元管理テスト
// ============================================================
test.describe('FEAT-0014: 受注元管理', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-007: 受注元一覧ページにテーブルが正しいカラムヘッダーで表示される', async ({ page }) => {
    await page.goto('/order-sources')
    await page.waitForLoadState('networkidle')

    // テーブルヘッダーの確認
    await expect(page.locator('th', { hasText: '受注元名' })).toBeVisible()
    await expect(page.locator('th', { hasText: 'コード' })).toBeVisible()
    await expect(page.locator('th', { hasText: '電話番号' })).toBeVisible()
    await expect(page.locator('th', { hasText: '郵便番号' })).toBeVisible()
    await expect(page.locator('th', { hasText: '住所' })).toBeVisible()
    await expect(page.locator('th', { hasText: 'ステータス' })).toBeVisible()
  })

  test('AC-008: 受注元一覧にシードデータの受注元が表示される', async ({ page }) => {
    await page.goto('/order-sources')
    await page.waitForLoadState('networkidle')

    // シードデータの受注元が表示される
    // seed.py or seed_orders.py で作成された受注元が存在する
    const tableBody = page.locator('tbody')
    const rows = tableBody.locator('tr')
    const rowCount = await rows.count()

    // 少なくとも1行はデータがある
    expect(rowCount).toBeGreaterThan(0)

    // 「該当する受注元がありません」が表示されていないこと
    await expect(page.locator('text=該当する受注元がありません')).not.toBeVisible()
  })

  test('AC-009: 受注元新規登録フォームから受注元を作成できる', async ({ page }) => {
    await page.goto('/order-sources')
    await page.waitForLoadState('networkidle')

    // 新規登録ボタンをクリック
    await page.getByRole('button', { name: '新規登録' }).click()
    await page.waitForLoadState('networkidle')

    // フォームが表示される
    await expect(page.locator('text=受注元登録')).toBeVisible()

    const uniqueCode = `E2E${Date.now().toString().slice(-6)}`

    // フォームに入力
    await page.getByLabel('受注元名').fill('E2Eテスト受注元')
    await page.getByLabel('コード').fill(uniqueCode)
    await page.getByLabel('APIキー').fill(`e2e-api-key-${uniqueCode}`)
    await page.getByLabel('電話番号').fill('03-9999-9999')
    await page.getByLabel('郵便番号').fill('100-0001')
    await page.getByLabel('都道府県').fill('東京都')
    await page.getByLabel('市区町村・番地').fill('千代田区1-1-1')
    await page.getByLabel('建物名').fill('テストビル')

    // 登録ボタンをクリック
    await page.getByRole('button', { name: '登録' }).click()

    // 受注元一覧ページに遷移する
    await page.waitForURL('/order-sources', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 作成した受注元が一覧に表示される
    await expect(page.locator('text=E2Eテスト受注元')).toBeVisible()
  })

  test('AC-010: 受注元の情報を編集して保存すると更新が反映される', async ({ page }) => {
    await page.goto('/order-sources')
    await page.waitForLoadState('networkidle')

    // 受注元一覧から最初の行をクリック
    const firstRow = page.locator('tbody tr').first()
    const originalName = await firstRow.locator('td').first().textContent()
    await firstRow.click()
    await page.waitForLoadState('networkidle')

    // 編集フォームが表示される
    await expect(page.locator('text=受注元編集')).toBeVisible()

    // 電話番号を変更
    const phoneInput = page.getByLabel('電話番号')
    await phoneInput.clear()
    await phoneInput.fill('03-8888-7777')

    // 更新ボタンをクリック
    await page.getByRole('button', { name: '更新' }).click()

    // 受注元一覧ページに遷移する
    await page.waitForURL('/order-sources', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 更新した受注元の行をクリックして変更を確認
    await page.locator('tbody tr').first().click()
    await page.waitForLoadState('networkidle')

    // 変更後の電話番号が表示される
    const updatedPhone = await page.getByLabel('電話番号').inputValue()
    expect(updatedPhone).toBe('03-8888-7777')

    // 元の値に戻す（テストの独立性のため）
    const phoneInputRestore = page.getByLabel('電話番号')
    await phoneInputRestore.clear()
    await phoneInputRestore.fill('03-1111-2222')
    await page.getByRole('button', { name: '更新' }).click()
    await page.waitForURL('/order-sources', { timeout: 10000 })
  })
})
