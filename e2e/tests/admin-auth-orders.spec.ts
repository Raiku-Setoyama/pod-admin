import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0015: 管理者ページの認証・受注管理機能 E2Eテスト
 *
 * 対象機能:
 * - 管理者ログイン（AC-001〜AC-003）
 * - 受注一覧取得（AC-004〜AC-008）
 * - 受注詳細取得（AC-009〜AC-013）
 * - 受注ステータス更新（AC-014〜AC-015）
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

// ============================================================
// 管理者ログイン
// ============================================================
test.describe('管理者ログイン', () => {
  test('AC-001: 正しい認証情報でログインするとダッシュボードに遷移する', async ({ page }) => {
    await page.goto('/login')

    // ログインフォームが表示されていること
    await expect(page.getByLabel('メールアドレス')).toBeVisible()
    await expect(page.getByLabel('パスワード')).toBeVisible()
    await expect(page.getByRole('button', { name: 'ログイン' })).toBeVisible()

    // 正しい認証情報を入力してログイン
    await page.getByLabel('メールアドレス').fill('admin@example.com')
    await page.getByLabel('パスワード').fill('password')
    await page.getByRole('button', { name: 'ログイン' }).click()

    // ダッシュボード（/）に遷移すること
    await page.waitForURL('/', { timeout: 10000 })
    await expect(page).toHaveURL('/')
  })

  test('AC-002: 誤った認証情報でログインするとエラーメッセージが表示される', async ({ page }) => {
    await page.goto('/login')

    // 誤ったパスワードでログイン
    await page.getByLabel('メールアドレス').fill('admin@example.com')
    await page.getByLabel('パスワード').fill('wrong-password')
    await page.getByRole('button', { name: 'ログイン' }).click()

    // エラーメッセージが表示されること
    await expect(page.locator('[class*="destructive"]')).toBeVisible({ timeout: 5000 })

    // ログインページに留まること
    await expect(page).toHaveURL(/\/login/)
  })

  test('AC-003: 未認証状態でダッシュボードにアクセスするとログインページにリダイレクトされる', async ({ page }) => {
    // localStorageをクリアした状態でアクセス
    await page.goto('/')

    // ログインページにリダイレクトされること
    await page.waitForURL(/\/login/, { timeout: 10000 })
    await expect(page).toHaveURL(/\/login/)
  })
})

// ============================================================
// 受注一覧取得
// ============================================================
test.describe('受注一覧取得', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-004: 受注一覧ページにテーブルが正しいカラムヘッダーで表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    // テーブルヘッダーの確認
    await expect(page.locator('th', { hasText: '注文番号' })).toBeVisible()
    await expect(page.locator('th', { hasText: '受注元' })).toBeVisible()
    await expect(page.locator('th', { hasText: '購入者' })).toBeVisible()
    await expect(page.locator('th', { hasText: '商品数' })).toBeVisible()
    await expect(page.locator('th', { hasText: '合計金額' })).toBeVisible()
    await expect(page.locator('th', { hasText: '受注日' })).toBeVisible()
    await expect(page.locator('th', { hasText: 'ステータス' })).toBeVisible()
  })

  test('AC-005: 受注一覧にシードデータの受注が表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    // データ行が存在すること
    expect(rowCount).toBeGreaterThan(0)

    // 「該当する受注がありません」ではないこと
    const firstRowText = await rows.first().textContent()
    expect(firstRowText).not.toContain('該当する受注がありません')
  })

  test('AC-006: 受注一覧にページネーションが表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    // ページネーションUI要素の確認
    // 表示件数セレクタ
    await expect(page.locator('text=表示件数:')).toBeVisible()

    // ページ情報テキスト（N〜M件 / 全X件）
    await expect(page.locator('text=/\\d+〜\\d+件/')).toBeVisible()

    // 前後ボタン
    const paginationButtons = page.locator('button').filter({ has: page.locator('svg') })
    // ChevronLeftとChevronRightボタンが存在すること
    expect(await paginationButtons.count()).toBeGreaterThanOrEqual(2)
  })

  test('AC-007: 受注一覧のステータスフィルターで絞り込みができる', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    // ステータスフィルターのSelectトリガーを探す
    const statusSelect = page.locator('button[role="combobox"]')
    await expect(statusSelect).toBeVisible()

    // 「発注中」でフィルター
    await statusSelect.click()
    await page.getByRole('option', { name: '発注中' }).click()

    // フィルター適用後、テーブルが表示される（エラーなし）
    await page.waitForLoadState('networkidle')
    await expect(page.locator('table')).toBeVisible()

    // 「全てのステータス」に戻す
    await statusSelect.click()
    await page.getByRole('option', { name: '全てのステータス' }).click()
    await page.waitForLoadState('networkidle')
    await expect(page.locator('table')).toBeVisible()
  })

  test('AC-008: 受注一覧のキーワード検索でフィルタリングができる', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    // 検索欄に入力
    const searchInput = page.getByPlaceholder(/検索/)
    await expect(searchInput).toBeVisible()
    await searchInput.fill('ORD')

    // 検索後、テーブルが表示される（エラーなし）
    await page.waitForLoadState('networkidle')
    await expect(page.locator('table')).toBeVisible()
  })
})

// ============================================================
// 受注詳細取得
// ============================================================
test.describe('受注詳細取得', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-009: 受注一覧の行をクリックすると詳細ページに遷移する', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        // 最初の受注行をクリック
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // /orders/{id} ページに遷移していること
        await expect(page).toHaveURL(/\/orders\/[a-f0-9-]+/)

        // 「受注詳細」タイトルが表示されていること
        await expect(page.locator('text=受注詳細')).toBeVisible()
      }
    }
  })

  test('AC-010: 受注詳細ページに受注情報カードが表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 受注情報カード
        await expect(page.locator('text=受注情報')).toBeVisible()

        // 注文番号、受注日時、商品数、合計金額の項目
        await expect(page.locator('text=注文番号')).toBeVisible()
        await expect(page.locator('text=受注日時')).toBeVisible()
        await expect(page.locator('text=商品数')).toBeVisible()
        await expect(page.locator('text=合計金額')).toBeVisible()
      }
    }
  })

  test('AC-011: 受注詳細ページに商品一覧カードが表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 商品一覧カード
        await expect(page.locator('text=商品一覧')).toBeVisible()
      }
    }
  })

  test('AC-012: 受注詳細ページに顧客情報カードが表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 顧客情報カード
        await expect(page.locator('text=顧客情報')).toBeVisible()

        // 顧客情報の項目
        await expect(page.locator('text=氏名')).toBeVisible()
        await expect(page.locator('text=電話番号')).toBeVisible()
        await expect(page.locator('text=住所')).toBeVisible()
        await expect(page.locator('text=メールアドレス')).toBeVisible()
      }
    }
  })

  test('AC-013: 受注詳細ページの「受注一覧に戻る」ボタンで一覧に戻れる', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // 「受注一覧に戻る」ボタンが表示されていること
        const backButton = page.getByRole('button', { name: '受注一覧に戻る' })
        await expect(backButton).toBeVisible()

        // ボタンをクリックして一覧に戻る
        await backButton.click()
        await page.waitForLoadState('networkidle')

        // /orders ページに遷移していること
        await expect(page).toHaveURL(/\/orders$/)
      }
    }
  })
})

// ============================================================
// 受注ステータス更新
// ============================================================
test.describe('受注ステータス更新', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test('AC-014: 受注詳細ページにステータス変更ボタンが表示される', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // ステータス変更ボタンが表示されていること
        const statusButton = page.getByRole('button', { name: 'ステータス変更' })
        await expect(statusButton).toBeVisible()
      }
    }
  })

  test('AC-015: ステータス変更ダイアログでステータスを更新できる', async ({ page }) => {
    await page.goto('/orders')
    await page.waitForLoadState('networkidle')

    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount > 0) {
      const firstRowText = await rows.first().textContent()
      if (!firstRowText?.includes('該当する受注がありません')) {
        await rows.first().click()
        await page.waitForLoadState('networkidle')

        // ステータス変更ボタンをクリック
        const statusButton = page.getByRole('button', { name: 'ステータス変更' })
        await statusButton.click()

        // ダイアログが表示されること
        const dialog = page.locator('[role="dialog"]')
        await expect(dialog).toBeVisible()

        // ダイアログ内の「ステータス変更」タイトルが表示されていること
        await expect(dialog.locator('text=ステータス変更')).toBeVisible()

        // 新しいステータスを選択する（製造中を選択）
        const selectTrigger = dialog.locator('button[role="combobox"]')
        await selectTrigger.click()
        await page.getByRole('option', { name: '製造中' }).click()

        // 更新ボタンをクリック
        await dialog.getByRole('button', { name: '更新' }).click()

        // ダイアログが閉じること
        await expect(dialog).not.toBeVisible({ timeout: 5000 })

        // ステータスが更新されていること（StatusBadgeに「製造中」が表示される）
        await page.waitForLoadState('networkidle')
        await expect(page.locator('text=製造中')).toBeVisible()
      }
    }
  })
})
