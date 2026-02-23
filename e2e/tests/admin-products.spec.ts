import { test, expect, type Page } from '@playwright/test'

/**
 * FEAT-0016: 商品管理ページE2Eテスト
 * 商品一覧・作成・詳細・更新・削除・種別マスタ管理の全機能をE2Eで検証する
 */

async function loginAsAdmin(page: Page) {
  await page.goto('/login')
  await page.getByLabel('メールアドレス').fill('admin@example.com')
  await page.getByLabel('パスワード').fill('password')
  await page.getByRole('button', { name: 'ログイン' }).click()
  await page.waitForURL('/', { timeout: 10000 })
}

test.describe('FEAT-0016: 商品管理', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsAdmin(page)
  })

  test.describe('商品一覧表示', () => {
    test('AC-001: 商品一覧ページにテーブルが正しいカラムヘッダーで表示される', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      // テーブルヘッダーの確認
      const headers = ['種類', 'サイズ/位置/カラー', 'メーカー', '原価', 'リードタイム', 'ステータス']
      for (const header of headers) {
        await expect(page.locator('th', { hasText: header })).toBeVisible()
      }
    })

    test('AC-002: 商品一覧にシードデータの商品が表示される', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      // シードデータにTシャツが存在するか確認
      const rows = page.locator('tbody tr')
      const rowCount = await rows.count()
      expect(rowCount).toBeGreaterThan(0)

      // Tシャツがテーブルに表示されていること
      await expect(page.locator('tbody').getByText('Tシャツ').first()).toBeVisible()
    })

    test('AC-003: 商品一覧にページネーションが表示される', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      // 表示件数セレクタが存在すること
      await expect(page.getByText('表示件数:')).toBeVisible()

      // ページ情報が表示されること（例: "1〜12件 / 全12件"）
      await expect(page.locator('text=/\\d+〜\\d+件/')).toBeVisible()
    })
  })

  test.describe('商品作成', () => {
    test('AC-004: 新規商品ページに遷移し、フォームが表示される', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      // 「新規商品」ボタンをクリック
      await page.getByRole('button', { name: '新規商品' }).click()
      await page.waitForURL('/products/new')

      // タイトルが表示されること
      await expect(page.getByText('商品新規登録')).toBeVisible()

      // フォームカードが表示されること
      await expect(page.getByText('基本情報')).toBeVisible()
      await expect(page.getByText('製造情報')).toBeVisible()
    })

    test('AC-005: 商品フォームに必要項目を入力して登録できる', async ({ page }) => {
      await page.goto('/products/new')
      await page.waitForLoadState('networkidle')

      // 商品種別を選択（ステッカーを選択）
      const productTypeSelect = page.locator('button[role="combobox"]').first()
      await productTypeSelect.click()
      await page.getByRole('option', { name: 'ステッカー' }).click()

      // サイズを入力
      await page.getByLabel('サイズ（任意）').fill('E2E-TEST-200x200mm')

      // 原価を入力
      const costInput = page.getByLabel('原価（円）')
      await costInput.clear()
      await costInput.fill('999')

      // リードタイムを入力
      const leadTimeInput = page.getByLabel('リードタイム（日）')
      await leadTimeInput.clear()
      await leadTimeInput.fill('5')

      // メーカーを選択（製造メーカーのセレクト）
      const manufacturerSelect = page.locator('button[role="combobox"]').nth(1)
      await manufacturerSelect.click()
      await page.getByRole('option', { name: 'シードット' }).click()

      // 登録ボタンをクリック
      await page.getByRole('button', { name: '登録' }).click()

      // 商品一覧に戻ること
      await page.waitForURL('/products', { timeout: 10000 })

      // 作成した商品が一覧に表示されること
      await page.waitForLoadState('networkidle')
      await expect(page.locator('tbody').getByText('E2E-TEST-200x200mm').first()).toBeVisible()
    })
  })

  test.describe('商品詳細取得', () => {
    test('AC-006: 商品一覧の行をクリックすると詳細ページに遷移する', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      const rows = page.locator('tbody tr')
      const rowCount = await rows.count()
      expect(rowCount).toBeGreaterThan(0)

      // 最初のデータ行をクリック
      const firstRow = rows.first()
      const firstRowText = await firstRow.textContent()

      if (!firstRowText?.includes('該当する商品がありません')) {
        await firstRow.click()
        await page.waitForURL(/\/products\/[a-f0-9-]+/)

        // 商品編集のタイトルが表示されること
        await expect(page.getByText('商品編集')).toBeVisible()
      }
    })

    test('AC-007: 商品詳細ページにフォームが正しく表示され、既存データがロードされている', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      const rows = page.locator('tbody tr')
      await rows.first().click()
      await page.waitForURL(/\/products\/[a-f0-9-]+/)
      await page.waitForLoadState('networkidle')

      // カードが表示されていること
      await expect(page.getByText('基本情報')).toBeVisible()
      await expect(page.getByText('製造情報')).toBeVisible()

      // フォームフィールドにデータがロードされていること
      // 原価フィールドに値が入力されていること
      const costInput = page.getByLabel('原価（円）')
      const costValue = await costInput.inputValue()
      expect(parseInt(costValue)).toBeGreaterThan(0)

      // リードタイムフィールドに値が入力されていること
      const leadTimeInput = page.getByLabel('リードタイム（日）')
      const leadTimeValue = await leadTimeInput.inputValue()
      expect(parseInt(leadTimeValue)).toBeGreaterThan(0)
    })

    test('AC-008: 商品詳細ページに「商品一覧に戻る」ボタンが表示され、クリックで一覧に戻れる', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      const rows = page.locator('tbody tr')
      await rows.first().click()
      await page.waitForURL(/\/products\/[a-f0-9-]+/)
      await page.waitForLoadState('networkidle')

      // 「商品一覧に戻る」ボタンが表示されていること
      const backButton = page.getByRole('button', { name: '商品一覧に戻る' })
      await expect(backButton).toBeVisible()

      // クリックで一覧に戻れること
      await backButton.click()
      await page.waitForURL('/products')
    })
  })

  test.describe('商品更新', () => {
    test('AC-009: 商品詳細ページで原価を変更して保存すると更新が反映される', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      // 最初の商品をクリック
      const rows = page.locator('tbody tr')
      await rows.first().click()
      await page.waitForURL(/\/products\/[a-f0-9-]+/)
      await page.waitForLoadState('networkidle')

      // 現在のURLを記録
      const productUrl = page.url()

      // 原価フィールドの値を取得して変更
      const costInput = page.getByLabel('原価（円）')
      const originalCost = await costInput.inputValue()
      const newCost = String(parseInt(originalCost) + 1)

      await costInput.clear()
      await costInput.fill(newCost)

      // 更新ボタンをクリック
      await page.getByRole('button', { name: '更新' }).click()

      // 商品一覧に戻ること
      await page.waitForURL('/products', { timeout: 10000 })

      // 再度同じ商品を開いて変更が反映されていることを確認
      await page.goto(productUrl)
      await page.waitForLoadState('networkidle')

      const updatedCostValue = await page.getByLabel('原価（円）').inputValue()
      expect(updatedCostValue).toBe(newCost)

      // 元の値に復元
      await page.getByLabel('原価（円）').clear()
      await page.getByLabel('原価（円）').fill(originalCost)
      await page.getByRole('button', { name: '更新' }).click()
      await page.waitForURL('/products', { timeout: 10000 })
    })
  })

  test.describe('商品削除', () => {
    test('AC-010: 商品詳細ページに削除ボタンが表示される', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      const rows = page.locator('tbody tr')
      await rows.first().click()
      await page.waitForURL(/\/products\/[a-f0-9-]+/)
      await page.waitForLoadState('networkidle')

      // 削除ボタンが表示されていること
      await expect(page.getByRole('button', { name: '削除' })).toBeVisible()
    })

    test('AC-011: 削除ボタンをクリックすると確認ダイアログが表示され、確認後に商品が削除される', async ({ page }) => {
      // まずE2Eテスト用の商品を作成
      await page.goto('/products/new')
      await page.waitForLoadState('networkidle')

      // ステッカーを選択
      const productTypeSelect = page.locator('button[role="combobox"]').first()
      await productTypeSelect.click()
      await page.getByRole('option', { name: 'ステッカー' }).click()

      // ユニークなサイズを設定（削除テスト用）
      await page.getByLabel('サイズ（任意）').fill('E2E-DELETE-TEST')

      // 原価を入力
      const costInput = page.getByLabel('原価（円）')
      await costInput.clear()
      await costInput.fill('100')

      // リードタイムを入力
      const leadTimeInput = page.getByLabel('リードタイム（日）')
      await leadTimeInput.clear()
      await leadTimeInput.fill('3')

      // メーカーを選択
      const manufacturerSelect = page.locator('button[role="combobox"]').nth(1)
      await manufacturerSelect.click()
      await page.getByRole('option', { name: 'シードット' }).click()

      // 登録ボタンをクリック
      await page.getByRole('button', { name: '登録' }).click()
      await page.waitForURL('/products', { timeout: 10000 })
      await page.waitForLoadState('networkidle')

      // 作成した商品が一覧に表示されること
      await expect(page.locator('tbody').getByText('E2E-DELETE-TEST').first()).toBeVisible()

      // 作成した商品をクリックして詳細ページへ
      await page.locator('tbody tr', { hasText: 'E2E-DELETE-TEST' }).first().click()
      await page.waitForURL(/\/products\/[a-f0-9-]+/)
      await page.waitForLoadState('networkidle')

      // 削除ボタンをクリック
      await page.getByRole('button', { name: '削除' }).click()

      // 確認ダイアログが表示されること
      await expect(page.getByText('商品を削除しますか？')).toBeVisible()

      // 「削除する」ボタンをクリック
      await page.getByRole('button', { name: '削除する' }).click()

      // 商品一覧に戻ること
      await page.waitForURL('/products', { timeout: 10000 })
      await page.waitForLoadState('networkidle')

      // 削除した商品が一覧から消えていること
      await expect(page.locator('tbody').getByText('E2E-DELETE-TEST')).not.toBeVisible()
    })
  })

  test.describe('商品種別マスタ管理', () => {
    test('AC-012: 商品フォームの種別セレクトボックスに全商品種別が表示される', async ({ page }) => {
      await page.goto('/products/new')
      await page.waitForLoadState('networkidle')

      // 商品種別セレクトボックスを開く
      const productTypeSelect = page.locator('button[role="combobox"]').first()
      await productTypeSelect.click()

      // 全5種類の商品種別が選択肢として表示されること
      const expectedTypes = [
        'アクリルキーホルダー',
        'アクリルスタンド',
        'ステッカー',
        'トートバッグ',
        'Tシャツ',
      ]

      for (const typeName of expectedTypes) {
        await expect(page.getByRole('option', { name: typeName })).toBeVisible()
      }
    })
  })

  test.describe('クリーンアップ', () => {
    test('AC-005で作成したテスト商品を削除する', async ({ page }) => {
      await page.goto('/products')
      await page.waitForLoadState('networkidle')

      // E2E-TEST-200x200mm の商品が存在する場合、削除する
      const testProduct = page.locator('tbody tr', { hasText: 'E2E-TEST-200x200mm' })
      const count = await testProduct.count()

      if (count > 0) {
        await testProduct.first().click()
        await page.waitForURL(/\/products\/[a-f0-9-]+/)
        await page.waitForLoadState('networkidle')

        // 削除ボタンをクリック
        await page.getByRole('button', { name: '削除' }).click()
        await expect(page.getByText('商品を削除しますか？')).toBeVisible()
        await page.getByRole('button', { name: '削除する' }).click()
        await page.waitForURL('/products', { timeout: 10000 })
      }
    })
  })
})
