import { expect, test } from "@playwright/test";

import { login } from "./support/mockApi";

test("admin sees the complete enterprise control plane", async ({ page }) => {
  await login(page, "admin");
  await expect(page.getByText("用户管理", { exact: true })).toBeVisible();
  await expect(page.getByText("审计日志", { exact: true })).toBeVisible();
  await expect(page.getByText("系统健康", { exact: true })).toBeVisible();
});

test("engineer can inspect health but cannot access identity or audit", async ({ page }) => {
  await login(page, "engineer");
  await expect(page.getByText("系统健康", { exact: true })).toBeVisible();
  await expect(page.getByText("用户管理", { exact: true })).toHaveCount(0);
  await expect(page.getByText("审计日志", { exact: true })).toHaveCount(0);
  await page.goto("/admin/audit-logs");
  await expect(page.getByText("当前角色无权访问", { exact: true })).toBeVisible();
});

test("viewer only sees chat and knowledge navigation", async ({ page }) => {
  await login(page, "viewer");
  await expect(page.getByText("RAG 对话", { exact: true })).toBeVisible();
  await expect(page.getByText("知识库", { exact: true })).toBeVisible();
  await expect(page.getByText("RAG 评估", { exact: true })).toHaveCount(0);
  await expect(page.getByText("可观测性", { exact: true })).toHaveCount(0);
  await expect(page.getByText("系统健康", { exact: true })).toHaveCount(0);
});
