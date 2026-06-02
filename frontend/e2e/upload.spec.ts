import { test, expect } from "@playwright/test";

test.describe("Nexus RAG - Document Ingestion Control Room", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.locator("button:has-text('Developer Bypass')").click();
  });

  test("should switch tabs to Ingestion and render upload drop zone", async ({ page }) => {
    // Click on Ingestion Jobs sidebar button
    const ingestionTabBtn = page.locator("button:has-text('Ingestion Jobs')");
    await expect(ingestionTabBtn).toBeVisible();
    await ingestionTabBtn.click();

    // Verify Ingestion Dashboard header is visible
    await expect(page.locator("h2:has-text('Document Ingestion Control Room')")).toBeVisible();

    // Verify drop zone is rendered
    await expect(page.locator("text=Drag & Drop document or Click to Browse")).toBeVisible();
    
    // Verify empty state document list text is present
    await expect(page.locator("text=No documents in the system database.")).toBeVisible();
  });
});
