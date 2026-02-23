import { test, expect } from '@playwright/test'

test.describe('Example E2E Tests', () => {
  test('should load the home page', async ({ page }) => {
    await page.goto('/')
    await expect(page).toHaveURL('/')
  })

  test('should have correct title', async ({ page }) => {
    await page.goto('/')
    // Update this to match your actual page title
    await expect(page).toHaveTitle(/.+/)
  })
})
