import { expect, test } from "@playwright/test";

import { login } from "./support/mockApi";

test("admin inspects users, audit events, and service readiness", async ({ page }) => {
  await login(page, "admin");

  await page.getByText("用户管理", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "用户与角色管理" })).toBeVisible();
  await expect(page.getByText("quality_engineer", { exact: true })).toBeVisible();

  await page.getByText("审计日志", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "操作审计日志" })).toBeVisible();
  await expect(page.getByText("request-e2e-001", { exact: true })).toBeVisible();

  await page.getByText("系统健康", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "系统健康状态" })).toBeVisible();
  await expect(page.getByText("PostgreSQL", { exact: true })).toBeVisible();
  await expect(page.getByText("READY", { exact: true }).first()).toBeVisible();
});
