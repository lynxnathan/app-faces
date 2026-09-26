import { homedir } from "node:os";
import { join } from "node:path";
import { firefox, expect } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
const browser = await firefox.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
try {
  await page.goto("https://app-faces-catalog.lynxnathan.workers.dev/admin");
  await expect(
    page.getByLabel("Access password", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../state/admin-production-login.png",
    fullPage: true,
  });
  await page
    .getByLabel("Access password", { exact: true })
    .fill(
      (
        await readFile(
          join(homedir(), ".config/app-faces/moderator-token"),
          "utf8",
        )
      ).trim(),
    );
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Review queue", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "History", exact: true }).click();
  await expect(page.locator("#details")).not.toHaveAttribute(
    "aria-busy",
    "true",
  );
  await expect(page.locator("#message")).toBeEmpty();
  await page.screenshot({
    path: "../state/admin-production-history.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Catalog versions", exact: true })
    .click();
  await expect(page.getByText("Latest")).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByLabel("Access password", { exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
  const result = {
    checkedAt: new Date().toISOString(),
    endpoint: "https://app-faces-catalog.lynxnathan.workers.dev/admin",
    browser: "Firefox",
    checks: [
      "published login",
      "authenticated queue",
      "history",
      "catalog revisions",
      "logout",
      "no uncaught browser errors",
    ],
    passed: true,
    mutations: false,
  };
  await writeFile(
    "../state/production-ui-smoke.json",
    JSON.stringify(result, null, 2) + "\n",
  );
  console.log("Published Firefox UI: 6 checks passed; no catalog writes.");
} finally {
  await browser.close();
}
