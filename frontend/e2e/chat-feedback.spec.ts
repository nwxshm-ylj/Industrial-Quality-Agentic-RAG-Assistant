import { expect, test } from "@playwright/test";

import { login } from "./support/mockApi";

test("viewer completes a traceable chat and submits feedback", async ({ page }) => {
  await login(page, "viewer");
  await page.getByText("RAG 对话", { exact: true }).click();
  await page.getByLabel("输入工业质量问题").fill("轮毂识别异常可能是什么原因？");
  await page.getByRole("button", { name: "发送问题" }).click();

  await expect(page.getByText("建议优先检查相机曝光、轮毂型号配置和识别区域遮挡。")).toBeVisible();
  await expect(page.getByText("request-e2e-001", { exact: false })).toBeVisible();
  await page.getByRole("button", { name: /有用/ }).click();
  await page.getByPlaceholder("补充反馈备注（可选），例如：引用准确但排查顺序不够具体").fill("引用和排查顺序清晰");
  await page.getByRole("button", { name: "提交反馈" }).click();
  await expect(page.getByText("已记录为“有用”", { exact: false })).toBeVisible();
});
