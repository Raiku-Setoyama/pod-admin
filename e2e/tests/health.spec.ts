import { test, expect } from "@playwright/test";

test.describe("ヘルスチェック", () => {
  test("トップページが表示される", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/.*/);
  });

  test("APIヘルスエンドポイントが応答する", async ({ request }) => {
    const apiUrl = process.env.API_URL || "http://localhost:8000";
    const response = await request.get(`${apiUrl}/health`);
    expect(response.ok()).toBeTruthy();
  });
});
