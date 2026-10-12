import { test, expect } from "@playwright/test";
import path from "path";

test("full MVP flow: upload → extract → confirm → calculate → decision", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Создать сделку" }).click();
  await expect(page.getByText(/Сделка #/)).toBeVisible();

  const fixture = path.resolve(process.cwd(), "tests/fixtures/demo.xlsx");
  await page.locator('input[type="file"]').setInputFiles(fixture);

  await expect(page.getByRole("heading", { name: "Сверка документов" })).toBeVisible();
  await page.getByRole("button", { name: "Распознать и извлечь требования" }).click();

  await expect(page.getByRole("heading", { name: "Карточка требований" })).toBeVisible();
  await expect(page.getByText("Площадь", { exact: true })).toBeVisible();

  const areaCard = page.locator(".field").filter({ hasText: "Площадь" });
  await areaCard.getByRole("button", { name: "Подтвердить" }).click();
  await expect(areaCard.getByRole("button", { name: "✓ Подтверждено" })).toBeVisible();

  await page.getByRole("button", { name: "К расчёту →" }).click();
  await expect(page.getByRole("heading", { name: "Параметры расчёта" })).toBeVisible();

  await page.getByRole("button", { name: "Рассчитать трудоёмкость и экономику" }).click();
  await expect(page.getByRole("heading", { name: "Экономика контракта" })).toBeVisible();
  await expect(page.getByText("Break-even")).toBeVisible();

  await page.getByRole("button", { name: "К решению →" }).click();
  await expect(page.getByRole("heading", { name: "Коммерческое решение" })).toBeVisible();
  await expect(page.locator(".decisionHero")).toContainText(/BID|NO BID/);

  await page.getByRole("button", { name: "Контроль" }).click();
  await expect(page.getByRole("heading", { name: "Пошаговый контроль обработки" })).toBeVisible();
  await expect(page.getByText("deterministic_calculation")).toBeVisible();
});
