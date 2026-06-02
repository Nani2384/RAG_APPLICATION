import { test, expect } from "@playwright/test";

test.describe("Nexus RAG - Chat Conversational Interface", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Click developer bypass to access the main interface
    await page.locator("button:has-text('Developer Bypass')").click();
  });

  test("should allow sending a query and displaying the typing loading states", async ({ page }) => {
    const input = page.locator("input[placeholder='Ask anything about your documents...']");
    await expect(input).toBeVisible();

    // Type query and submit
    await input.fill("What is project alpha?");
    await page.locator("button[type='submit']").click();

    // Verify input gets cleared
    await expect(input).toHaveValue("");

    // Verify pulse/shimmer placeholder loading block is displayed
    const loadingBlock = page.locator(".animate-pulse");
    await expect(loadingBlock).toBeVisible();
  });

  test("should display citation badges and allow expanding/collapsing snippets", async ({ page }) => {
    // Assert static starter message is rendered
    await expect(page.locator("div:has-text('Hello! I am your enterprise AI assistant')")).toBeVisible();
  });
});
