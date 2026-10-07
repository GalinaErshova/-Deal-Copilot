import { test, expect } from "@playwright/test";

test("user can create a deal and reach calculation UI", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Создать сделку" }).click();
  await expect(page.getByText(/Сделка #/)).toBeVisible();

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles({
    name: "demo.xlsx",
    mimeType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: Buffer.from(
      "UEsDBAoAAAAAA", // deliberately invalid xlsx: UI upload path only; parser is covered by backend integration
      "utf8"
    ),
  });

  await page.getByRole("button", { name: "Требования" }).click();
  await expect(page.getByRole("heading", { name: "Карточка требований" })).toBeVisible();

  await page.getByRole("button", { name: "Трудоёмкость" }).click();
  await expect(page.getByRole("heading", { name: "Параметры расчёта" })).toBeVisible();
});
