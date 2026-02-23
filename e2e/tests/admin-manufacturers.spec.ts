import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0014: メーカー管理ページ E2Eテスト
 * メーカー一覧取得・作成・詳細取得・情報更新・削除の全機能を検証
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

test.describe('FEAT-0014: メーカー管理', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  // ================================================================
  // メーカー一覧表示 (AC-001, AC-002, AC-003)
  // ================================================================

  test('AC-001: メーカー一覧ページにテーブルが正しいカラムヘッダーで表示される', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // テーブルヘッダーの確認
    await expect(page.locator('th', { hasText: 'メーカー名' })).toBeVisible()
    await expect(page.locator('th', { hasText: '連絡先' })).toBeVisible()
    await expect(page.locator('th', { hasText: '対応商品' })).toBeVisible()
    await expect(page.locator('th', { hasText: '1日上限' })).toBeVisible()
    await expect(page.locator('th', { hasText: '共有方式' })).toBeVisible()
    await expect(page.locator('th', { hasText: 'ステータス' })).toBeVisible()
    await expect(page.locator('th', { hasText: 'チャット' })).toBeVisible()
  })

  test('AC-002: メーカー一覧にシードデータのメーカーが表示される', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードデータのメーカーが表示されること
    await expect(page.locator('td', { hasText: 'シードット' })).toBeVisible()
  })

  test('AC-003: メーカー一覧にページネーションが表示される', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // ページネーションUI の確認
    await expect(page.locator('text=表示件数:')).toBeVisible()
    // ページ情報の表示（例: 1〜2件 / 全2件）
    await expect(page.locator('text=/\\d+〜\\d+件/')).toBeVisible()
  })

  // ================================================================
  // メーカー作成 (AC-004, AC-005)
  // ================================================================

  test('AC-004: 新規メーカーボタンをクリックすると作成ページに遷移する', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // 「新規メーカー」ボタンをクリック
    await page.getByRole('button', { name: '新規メーカー' }).click()
    await page.waitForURL('/manufacturers/new', { timeout: 10000 })

    // 新規メーカー登録ページが表示される
    await expect(page.locator('text=新規メーカー登録')).toBeVisible()

    // 空のフォームが表示される
    await expect(page.locator('text=基本情報')).toBeVisible()
    await expect(page.locator('text=対応商品')).toBeVisible()
    await expect(page.locator('text=発注設定')).toBeVisible()
  })

  test('AC-005: メーカー作成フォームに必要事項を入力して登録できる', async ({ page }) => {
    const testManufacturerName = `E2Eテストメーカー_${Date.now()}`

    await page.goto('/manufacturers/new')
    await page.waitForLoadState('networkidle')

    // 基本情報を入力
    await page.getByLabel('メーカー名').fill(testManufacturerName)
    await page.getByLabel('メールアドレス').fill('e2e-test@example.com')
    await page.getByLabel('電話番号（任意）').fill('03-0000-0000')

    // 対応商品を選択（アクリルキーホルダーのスイッチをON）
    const acrylicKeychainSwitch = page
      .locator('div', { hasText: /^アクリルキーホルダー$/ })
      .locator('button[role="switch"]')
    await acrylicKeychainSwitch.click()

    // 共有方式を「TOSYO DRIVE」に変更
    const sharingSelect = page.locator('button[role="combobox"]').first()
    await sharingSelect.click()
    await page.getByRole('option', { name: 'TOSYO DRIVE' }).click()

    // 登録ボタンをクリック
    await page.getByRole('button', { name: '登録' }).click()

    // メーカー一覧ページに遷移する
    await page.waitForURL('/manufacturers', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 一覧に作成したメーカーが表示される
    await expect(page.locator('td', { hasText: testManufacturerName })).toBeVisible()

    // テスト後のクリーンアップ: 作成したメーカーを削除
    // 作成したメーカーの行をクリックして詳細ページへ
    await page.locator('tr', { hasText: testManufacturerName }).click()
    await page.waitForLoadState('networkidle')

    // 削除ボタンをクリック
    await page.getByRole('button', { name: '削除' }).click()
    await page.waitForTimeout(500)

    // 確認ダイアログで削除を確定
    await page.getByRole('button', { name: '削除する' }).click()

    // 一覧ページに戻る
    await page.waitForURL('/manufacturers', { timeout: 10000 })
  })

  // ================================================================
  // メーカー詳細表示 (AC-006, AC-007, AC-008)
  // ================================================================

  test('AC-006: メーカー一覧の行をクリックすると詳細ページに遷移する', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードットの行をクリック
    await page.locator('tr', { hasText: 'シードット' }).click()

    // 詳細ページに遷移する
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })

    // メーカー編集タイトルが表示される
    await expect(page.locator('text=メーカー編集')).toBeVisible()
  })

  test('AC-007: メーカー詳細ページにフォームが正しく表示され、既存データがロードされている', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードットの行をクリック
    await page.locator('tr', { hasText: 'シードット' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // カードが表示される
    await expect(page.locator('text=基本情報')).toBeVisible()
    await expect(page.locator('text=対応商品')).toBeVisible()
    await expect(page.locator('text=発注設定')).toBeVisible()

    // メーカー名がフォームフィールドにロードされている
    const nameInput = page.getByLabel('メーカー名')
    await expect(nameInput).toHaveValue('シードット')

    // メールアドレスがロードされている
    const emailInput = page.getByLabel('メールアドレス')
    await expect(emailInput).toHaveValue('support@seedot.jp')
  })

  test('AC-008: メーカー詳細ページの「メーカー一覧に戻る」ボタンで一覧に戻れる', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードットの行をクリック
    await page.locator('tr', { hasText: 'シードット' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 「メーカー一覧に戻る」ボタンが表示される
    const backButton = page.getByRole('button', { name: 'メーカー一覧に戻る' })
    await expect(backButton).toBeVisible()

    // ボタンをクリック
    await backButton.click()

    // 一覧ページに遷移する
    await page.waitForURL('/manufacturers', { timeout: 10000 })
  })

  // ================================================================
  // メーカー情報更新 (AC-009, AC-010)
  // ================================================================

  test('AC-009: メーカー詳細ページでメーカー名を変更して保存すると更新が反映される', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードットの行をクリック
    await page.locator('tr', { hasText: 'シードット' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    const manufacturerUrl = page.url()

    // メーカー名を変更
    const nameInput = page.getByLabel('メーカー名')
    await nameInput.clear()
    await nameInput.fill('シードット_更新テスト')

    // 更新ボタンをクリック
    await page.getByRole('button', { name: '更新' }).click()

    // 一覧ページに遷移する
    await page.waitForURL('/manufacturers', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 変更後のメーカー名が表示される
    await expect(page.locator('td', { hasText: 'シードット_更新テスト' })).toBeVisible()

    // 元に戻す
    await page.locator('tr', { hasText: 'シードット_更新テスト' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    const nameInputRestore = page.getByLabel('メーカー名')
    await nameInputRestore.clear()
    await nameInputRestore.fill('シードット')

    await page.getByRole('button', { name: '更新' }).click()
    await page.waitForURL('/manufacturers', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 元のメーカー名が表示される
    await expect(page.locator('td', { hasText: 'シードット' })).toBeVisible()
  })

  test('AC-010: メーカー詳細ページで電話番号を変更して保存すると更新が反映される', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードットの行をクリック
    await page.locator('tr', { hasText: 'シードット' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 電話番号を変更
    const phoneInput = page.getByLabel('電話番号（任意）')
    const originalPhone = await phoneInput.inputValue()
    await phoneInput.clear()
    await phoneInput.fill('090-1111-2222')

    // 更新ボタンをクリック
    await page.getByRole('button', { name: '更新' }).click()

    // 一覧ページに遷移する
    await page.waitForURL('/manufacturers', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 再度詳細ページを開いて確認
    await page.locator('tr', { hasText: 'シードット' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 変更後の電話番号が表示される
    const phoneInputCheck = page.getByLabel('電話番号（任意）')
    await expect(phoneInputCheck).toHaveValue('090-1111-2222')

    // 元に戻す
    await phoneInputCheck.clear()
    await phoneInputCheck.fill(originalPhone || '03-1234-5678')

    await page.getByRole('button', { name: '更新' }).click()
    await page.waitForURL('/manufacturers', { timeout: 10000 })
  })

  // ================================================================
  // メーカー削除 (AC-011, AC-012)
  // ================================================================

  test('AC-011: メーカー詳細ページに削除ボタンが表示される', async ({ page }) => {
    await page.goto('/manufacturers')
    await page.waitForLoadState('networkidle')

    // シードットの行をクリック
    await page.locator('tr', { hasText: 'シードット' }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 削除ボタンが表示される
    await expect(page.getByRole('button', { name: '削除' })).toBeVisible()
  })

  test('AC-012: 削除ボタンをクリックすると確認ダイアログが表示され、確認後にメーカーが削除される', async ({ page }) => {
    // テスト用メーカーを先に作成する
    const testManufacturerName = `削除テスト用メーカー_${Date.now()}`

    await page.goto('/manufacturers/new')
    await page.waitForLoadState('networkidle')

    // 基本情報を入力
    await page.getByLabel('メーカー名').fill(testManufacturerName)
    await page.getByLabel('メールアドレス').fill('delete-test@example.com')

    // 対応商品を選択（アクリルキーホルダーのスイッチをON）
    const acrylicKeychainSwitch = page
      .locator('div', { hasText: /^アクリルキーホルダー$/ })
      .locator('button[role="switch"]')
    await acrylicKeychainSwitch.click()

    // 共有方式を「TOSYO DRIVE」に変更
    const sharingSelect = page.locator('button[role="combobox"]').first()
    await sharingSelect.click()
    await page.getByRole('option', { name: 'TOSYO DRIVE' }).click()

    // 登録
    await page.getByRole('button', { name: '登録' }).click()
    await page.waitForURL('/manufacturers', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 作成したメーカーが一覧に表示される
    await expect(page.locator('td', { hasText: testManufacturerName })).toBeVisible()

    // 作成したメーカーの行をクリック
    await page.locator('tr', { hasText: testManufacturerName }).click()
    await page.waitForURL(/\/manufacturers\/[a-f0-9-]+/, { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 削除ボタンをクリック
    await page.getByRole('button', { name: '削除' }).click()

    // 確認ダイアログが表示される
    await expect(page.locator('text=メーカーを削除しますか？')).toBeVisible()
    await expect(page.getByRole('button', { name: 'キャンセル' })).toBeVisible()
    await expect(page.getByRole('button', { name: '削除する' })).toBeVisible()

    // 削除を確定
    await page.getByRole('button', { name: '削除する' }).click()

    // 一覧ページに遷移する
    await page.waitForURL('/manufacturers', { timeout: 10000 })
    await page.waitForLoadState('networkidle')

    // 削除したメーカーが一覧に表示されない
    await expect(page.locator('td', { hasText: testManufacturerName })).not.toBeVisible()
  })
})
