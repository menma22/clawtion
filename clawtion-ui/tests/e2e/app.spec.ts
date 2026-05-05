import { test, expect } from '@playwright/test'

test.describe('clawtion App', () => {
  test('loads the app at root', async ({ page }) => {
    await page.goto('/')
    // Root path renders the notes page with heading
    await expect(page.getByRole('heading', { name: 'ノート' })).toBeVisible()
  })

  test('sidebar navigation works', async ({ page }) => {
    await page.goto('/notes')
    // Sidebar title should be visible
    await expect(page.locator('.font-semibold.text-sm.text-text-primary')).toBeVisible()

    // Navigate to search
    await page.click('text=検索')
    await expect(page).toHaveURL(/\/search/)

    // Navigate to settings
    await page.click('text=設定')
    await expect(page).toHaveURL(/\/settings/)

    // Navigate to queue
    await page.click('text=キュー')
    await expect(page).toHaveURL(/\/queue/)
  })

  test('settings page shows theme options', async ({ page }) => {
    await page.goto('/settings')
    await expect(page.locator('text=テーマ')).toBeVisible()
    await expect(page.locator('text=ライト')).toBeVisible()
    await expect(page.locator('text=ダーク')).toBeVisible()
  })

  test('search page has search input', async ({ page }) => {
    await page.goto('/search')
    const searchInput = page.getByPlaceholder(/検索/)
    await expect(searchInput).toBeVisible()
    // Verify search button exists
    const searchButton = page.locator('button:has-text("検索")')
    await expect(searchButton).toBeVisible()
  })

  test('queue page shows stats', async ({ page }) => {
    await page.goto('/queue')
    await expect(page.locator('text=キュー管理')).toBeVisible()
  })

  test('system page loads', async ({ page }) => {
    await page.goto('/system')
    await expect(page.locator('text=システム情報')).toBeVisible()
  })
})
