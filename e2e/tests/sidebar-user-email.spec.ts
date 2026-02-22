/**
 * サイドバー ユーザーメールアドレス表示 E2Eテスト
 *
 * Intent Spec: FEAT-0001
 * AC-001: サイドバーにログインユーザーのメールアドレスが表示される
 */
import { test, expect } from "@playwright/test";

test.describe("サイドバー - ログインユーザーのメールアドレス表示", () => {
  const API_URL = process.env.API_URL || "http://localhost:8000";

  test.beforeEach(async ({ page }) => {
    // テスト用ユーザーでログイン
    const loginResponse = await page.request.post(`${API_URL}/api/v1/auth/login`, {
      data: {
        email: "admin@example.com",
        password: "password123",
      },
    });

    if (loginResponse.ok()) {
      const tokens = await loginResponse.json();

      // localStorageにトークンを設定
      await page.goto("/");
      await page.evaluate((accessToken) => {
        localStorage.setItem("access_token", accessToken);
      }, tokens.access_token);
    }
  });

  test("AC-001: サイドバーにログインユーザーのメールアドレスが表示される", async ({ page }) => {
    // 管理画面に遷移
    await page.goto("/orders");

    // サイドバーが表示されるまで待機
    await page.waitForSelector("aside", { state: "visible" });

    // サイドバー内にログインユーザーのメールアドレスが表示されていることを確認
    const sidebar = page.locator("aside");

    // メールアドレスが表示されている（ハードコードではなく動的に取得されたもの）
    // ログインしたユーザーのメールアドレスが表示されることを確認
    await expect(sidebar.getByText("admin@example.com")).toBeVisible();
  });

  test("ハードコードされたメールアドレス「raiku6019@gmail.com」が表示されない", async ({ page }) => {
    await page.goto("/orders");

    await page.waitForSelector("aside", { state: "visible" });

    const sidebar = page.locator("aside");

    // ハードコードされたメールアドレスが存在しないことを確認
    await expect(sidebar.getByText("raiku6019@gmail.com")).not.toBeVisible();
  });

  test("異なるユーザーでログインした場合、そのユーザーのメールが表示される", async ({ page, request }) => {
    // 別のテストユーザーでログイン（staff@example.com など）
    const loginResponse = await request.post(`${API_URL}/api/v1/auth/login`, {
      data: {
        email: "staff@example.com",
        password: "password123",
      },
    });

    if (loginResponse.ok()) {
      const tokens = await loginResponse.json();

      await page.goto("/");
      await page.evaluate((accessToken) => {
        localStorage.setItem("access_token", accessToken);
      }, tokens.access_token);

      await page.goto("/orders");
      await page.waitForSelector("aside", { state: "visible" });

      const sidebar = page.locator("aside");

      // staffユーザーのメールアドレスが表示される
      await expect(sidebar.getByText("staff@example.com")).toBeVisible();

      // 他のユーザーのメールアドレスは表示されない
      await expect(sidebar.getByText("admin@example.com")).not.toBeVisible();
    }
  });

  test("ローディング中は適切な表示がされる", async ({ page }) => {
    // APIレスポンスを遅延させる
    await page.route(`${API_URL}/api/v1/auth/me`, async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.continue();
    });

    await page.goto("/orders");

    const sidebar = page.locator("aside");

    // ハードコードされたメールが表示されていないことを確認
    // （ローディング中もハードコードメールは表示されない）
    await expect(sidebar.getByText("raiku6019@gmail.com")).not.toBeVisible();
  });

  test("ページ遷移してもメールアドレスが維持される", async ({ page }) => {
    await page.goto("/orders");
    await page.waitForSelector("aside", { state: "visible" });

    const sidebar = page.locator("aside");
    await expect(sidebar.getByText("admin@example.com")).toBeVisible();

    // 別のページに遷移
    await page.click('a[href="/shipments"]');
    await page.waitForURL("/shipments");

    // サイドバーのメールアドレスは維持される
    await expect(sidebar.getByText("admin@example.com")).toBeVisible();
  });
});
