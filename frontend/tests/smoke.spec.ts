import { test, expect } from "@playwright/test";

const fixture = { name: "demo.txt", mimeType: "text/plain", buffer: Buffer.from("Общая площадь объекта 1200 м²") };

test("загрузка → извлечение → переход к требованиям", async ({ page }) => {
  await page.setViewportSize({width:1440,height:900});
  await page.addInitScript(() => localStorage.removeItem("dealCopilot.activeDealId"));
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await page.getByRole("button", { name: "Список сделок" }).click();
  await page.getByRole("button", { name: "Новая сделка", exact: true }).click();
  await expect(page.getByText(/Сделка #/).first()).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(fixture);

  await expect(page.getByRole("heading", { name: "Сверка документов" })).toBeVisible();
  await page.getByRole("button", { name: "Распознать и извлечь требования" }).click();

  await expect(page.getByRole("button", { name: "Свернуть документ" })).toBeVisible();
  await page.locator(".sectionActions").getByRole("button", { name: "Далее →" }).click();
  await expect(page.getByRole("heading", { name: "Карточка требований" })).toBeVisible();
  await expect(page.locator(".field").filter({ hasText: "Площадь" }).first()).toBeVisible();
});

test("на шаге документов можно удалить ошибочную загрузку", async ({ page }) => {
  await page.setViewportSize({width:390,height:844});
  await page.addInitScript(() => localStorage.removeItem("dealCopilot.activeDealId"));
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.getByRole("button", { name: "Список сделок" }).click();
  await page.getByRole("button", { name: "Новая сделка", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles(fixture);

  await expect(page.getByRole("button", { name: "Распознать и извлечь требования" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Переход между этапами" }).getByRole("button", { name: "Далее →" })).toBeDisabled();
  page.once("dialog", dialog => dialog.accept());
  await page.getByRole("button", { name: "Удалить документ demo.txt" }).click();
  await expect(page.getByRole("button", { name: "Удалить документ demo.txt" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Распознать и извлечь требования" })).toBeDisabled();
});
