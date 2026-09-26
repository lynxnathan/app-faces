import { firefox, expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
const [action, name, endpoint, credential, screenshot] = process.argv.slice(2);
if (
  !["approve", "revoke"].includes(action) ||
  !name ||
  !endpoint ||
  !credential
)
  throw Error("Expected action, fixture name, endpoint and credential file");
const browser = await firefox.launch();
try {
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  await page.goto(endpoint + "/admin");
  await page
    .getByLabel("Access password", { exact: true })
    .fill((await readFile(credential, "utf8")).trim());
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Review queue", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Contribution status")
    .selectOption(action === "approve" ? "pending" : "approved");
  await page.getByRole("searchbox").fill(name);
  await page
    .getByRole("button", { name: "Review " + name, exact: true })
    .click();
  await page
    .getByRole("button", {
      name: action === "approve" ? "Approve icon" : "Revoke icon",
      exact: true,
    })
    .click();
  await page
    .getByLabel("Decision reason")
    .fill(
      action === "approve"
        ? "Synthetic CC0 artwork for the native catalog flow."
        : "Test complete; remove synthetic catalog artwork.",
    );
  if (screenshot) await page.screenshot({ path: screenshot, fullPage: true });
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  await expect(page.locator("#message")).toContainText("Decision saved");
  console.log("Browser moderator action verified: " + action);
} finally {
  await browser.close();
}
