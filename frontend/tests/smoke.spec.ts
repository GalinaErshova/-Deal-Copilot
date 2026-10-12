import { test, expect } from "@playwright/test";
import path from "path";

const fixture = { name: "demo.txt", mimeType: "text/plain", buffer: Buffer.from("Общая площадь объекта 1200 м²") };

test("полный сценарий: загрузка → извлечение → подтверждение → расчёт → решение", async ({ page }) => {
  await page.setViewportSize({width:1440,height:900});
  await page.addInitScript(() => localStorage.removeItem("dealCopilot.activeDealId"));
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  await page.getByRole("button", { name: "Список сделок" }).click();
  await page.getByRole("button", { name: "Новая сделка", exact: true }).click();
  await expect(page.getByText(/Сделка #/).first()).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles(path.resolve(process.cwd(), "tests/fixtures/demo.xlsx"));

  await expect(page.getByRole("heading", { name: "Сверка документов" })).toBeVisible();
  await page.getByRole("button", { name: "Распознать и извлечь требования" }).click();

  await expect(page.getByRole("button", { name: "Свернуть документ" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Повторить извлечение" })).toBeVisible();
  await page.locator(".sectionActions").getByRole("button", { name: "Далее →" }).click();
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
