import { test, expect } from "@playwright/test";
import path from "path";

test("полный сценарий: загрузка → извлечение → подтверждение → расчёт → решение", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Создать сделку", exact: true }).click();
  await expect(page.getByText(/Сделка #/).first()).toBeVisible();

  const fixture = path.resolve(process.cwd(), "tests/fixtures/demo.xlsx");
  await page.locator('input[type="file"]').setInputFiles(fixture);

  await expect(page.getByRole("heading", { name: "Сверка документов" })).toBeVisible();
  await page.getByRole("button", { name: "Распознать и извлечь требования" }).click();

  await expect(page.getByRole("heading", { name: "Карточка требований" })).toBeVisible();
  const areaCard = page.locator(".field").filter({ hasText: "Площадь" }).first();
  await areaCard.getByRole("button", { name: "Подтвердить" }).click();
  await expect(areaCard.getByRole("button", { name: "✓ Подтверждено" })).toBeVisible();

  await page.getByRole("button", { name: "Настроить расчёт →" }).click();
  await expect(page.getByRole("heading", { name: "Параметры расчёта" })).toBeVisible();
  await page.getByLabel(/Подтверждаю расчёт целиком/).check();
  await page.getByRole("button", { name: "Рассчитать трудоёмкость и экономику" }).click();

  await expect(page.getByRole("heading", { name: "Экономика контракта" }).last()).toBeVisible();
  await expect(page.getByText("Тариф безубыточности")).toBeVisible();
  await expect(page.locator(".decisionHero")).toContainText(/BID|NO BID/);

  await page.getByRole("button", { name: /Контроль обработки/ }).click();
  await expect(page.getByRole("heading", { name: "Пошаговый контроль обработки" })).toBeVisible();
  await expect(page.getByText(/deterministic_calculation/).first()).toBeVisible();
});
