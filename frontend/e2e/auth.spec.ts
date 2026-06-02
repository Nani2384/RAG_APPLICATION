import { test, expect } from "@playwright/test";

test.describe("Nexus RAG - Authentication Flow", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the Next.js home page
    await page.goto("/");
  });

  test("should display the glassmorphic auth modal overlay on load if unauthenticated", async ({ page }) => {
    // Assert auth modal header is visible
    await expect(page.locator("h3:has-text('Access RAG Platform')")).toBeVisible();
    
    // Assert key login inputs are rendered
    await expect(page.locator("input[type='email']")).toBeVisible();
    await expect(page.locator("input[type='password']")).toBeVisible();
  });

  test("should allow developer bypass mode and render the dashboard layout", async ({ page }) => {
    // Locate and click the Developer Bypass button
    const bypassBtn = page.locator("button:has-text('Developer Bypass')");
    await expect(bypassBtn).toBeVisible();
    await bypassBtn.click();

    // Verify modal disappears
    await expect(page.locator("h3:has-text('Access RAG Platform')")).not.toBeVisible();

    // Verify main Nexus RAG layout is visible
    await expect(page.locator("h1:has-text('Nexus RAG')")).toBeVisible();
    await expect(page.locator("h2:has-text('Project Alpha Chat')")).toBeVisible();
  });

  test("should toggle between sign-in and registration modes cleanly", async ({ page }) => {
    const toggleBtn = page.locator("button:has-text('Need a tenant?')");
    await expect(toggleBtn).toBeVisible();
    await toggleBtn.click();

    // Verify header shifts to registration mode
    await expect(page.locator("h3:has-text('Create Secure Account')")).toBeVisible();
    await expect(page.locator("button[type='submit']:has-text('Register & Seed')")).toBeVisible();

    // Toggle back to login mode
    const toggleBackBtn = page.locator("button:has-text('Already have an account?')");
    await toggleBackBtn.click();
    await expect(page.locator("h3:has-text('Access RAG Platform')")).toBeVisible();
  });
});
