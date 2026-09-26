import AxeBuilder from "@axe-core/playwright";
import { test, expect, type Page } from "@playwright/test";
import { deflateSync } from "node:zlib";
import { randomUUID } from "node:crypto";
function chunk(type: string, data: Buffer): Buffer {
  const b = Buffer.concat([Buffer.from(type), data]);
  let crc = 0xffffffff;
  for (const x of b) {
    crc ^= x;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  const out = Buffer.alloc(b.length + 8);
  out.writeUInt32BE(data.length);
  b.copy(out, 4);
  out.writeUInt32BE((crc ^ 0xffffffff) >>> 0, out.length - 4);
  return out;
}
function icon(color = 99): string {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(64);
  header.writeUInt32BE(64, 4);
  header[8] = 8;
  header[9] = 6;
  const data = Buffer.alloc(64 * 257);
  for (let y = 0; y < 64; y++)
    for (let x = 0; x < 64; x++) {
      const offset = y * 257 + 1 + x * 4;
      data[offset] = color;
      data[offset + 1] = 91;
      data[offset + 2] = 255;
      data[offset + 3] = 255;
    }
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(data)),
    chunk("IEND", Buffer.alloc(0)),
  ]).toString("base64");
}
async function login(page: Page, password = "e2e-admin"): Promise<void> {
  await page.goto("/admin");
  await page.getByLabel("Access password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(
    page.getByRole("heading", { name: "Review queue", exact: true }),
  ).toBeVisible();
}
test("login, password visibility, invalid credentials and mobile layout", async ({
  page,
}) => {
  await page.goto("/admin");
  await page.screenshot({
    path: "../state/admin-login-desktop.png",
    fullPage: true,
  });
  await page.getByLabel("Access password", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "Show password" }).click();
  await expect(page.locator("#token")).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Hide password" }).click();
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid password");
  await expect(page.locator("#token")).toHaveValue("incorrect");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../state/admin-login-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("real upload → search → review → recover decision error → approve → history → restore → revoke", async ({
  page,
  request,
}) => {
  const name = "UI Review " + randomUUID().slice(0, 8);
  const response = await request.post("/v1/submissions", {
    headers: { "Idempotency-Key": randomUUID() },
    data: {
      applicationId: "org.appfaces.UiReview",
      name,
      sourceUrl: "https://example.org/artwork",
      license: "CC0-1.0",
      variant: "default",
      iconBase64: icon(),
    },
  });
  expect(response.status()).toBe(201);
  const proposal = (await response.json()) as { id: string };
  await login(page);
  await expect(
    page.getByRole("button", { name: "Review " + name }),
  ).toBeVisible();
  await page.getByRole("searchbox").fill("does not exist");
  await expect(page.getByText("No results.")).toBeVisible();
  await page.getByRole("searchbox").fill(name);
  await expect(page.locator(".icon-well img")).toBeVisible();
  await page.screenshot({
    path: "../state/admin-queue-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Review " + name }).click();
  await expect(page.getByRole("dialog", { name })).toBeVisible();
  await page.screenshot({
    path: "../state/admin-review-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Approve icon", exact: true }).click();
  await page
    .getByLabel("Decision reason")
    .fill("Synthetic artwork for interface testing.");
  await page.route(
    "**/admin/submissions/*/decision",
    (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          error: "Service temporarily unavailable.",
        }),
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision-error")).toContainText("unavailable");
  await expect(page.getByLabel("Decision reason")).toHaveValue(
    "Synthetic artwork for interface testing.",
  );
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  await expect(page.locator("#message")).toContainText("Decision saved");
  const status = await request.get("/admin/submissions?status=approved", {
    headers: { Authorization: "Bearer e2e-admin" },
  });
  expect(
    (
      (await status.json()) as { submissions: { id: string }[] }
    ).submissions.some((s) => s.id === proposal.id),
  ).toBe(true);
  await page.getByRole("button", { name: "History", exact: true }).click();
  await expect(
    page.getByText("Synthetic artwork for interface testing."),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Catalog versions", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Restore", exact: true })
    .first()
    .click();
  await page
    .getByLabel("Decision reason")
    .fill("Verify restoration through the browser.");
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  await page.getByRole("button", { name: "Review queue", exact: true }).click();
  await page.getByLabel("Contribution status").selectOption("approved");
  await page.getByRole("button", { name: "Review " + name }).click();
  await page.getByRole("button", { name: "Revoke icon", exact: true }).click();
  await page
    .getByLabel("Decision reason")
    .fill("Remove synthetic test artwork.");
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("searchbox").fill("");
  await page.screenshot({
    path: "../state/admin-queue-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(
    page.getByLabel("Access password", { exact: true }),
  ).toBeVisible();
});
test("reviewer cannot see administrator rollback controls and Escape closes dialogs", async ({
  page,
  request,
}) => {
  const name = "Reviewer " + randomUUID().slice(0, 8);
  const uploaded = await request.post("/v1/submissions", {
    headers: { "Idempotency-Key": randomUUID() },
    data: {
      applicationId: "org.appfaces.Reviewer",
      name,
      sourceUrl: "https://example.org/art",
      license: "CC0-1.0",
      variant: "default",
      iconBase64: icon(140),
    },
  });
  expect(uploaded.status()).toBe(201);
  await login(page, "e2e-reviewer");
  await page
    .getByRole("button", { name: "Catalog versions", exact: true })
    .click();
  await expect(page.getByText("Latest")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Restore", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Review queue", exact: true }).click();
  await page.getByRole("button", { name: "Review " + name }).click();
  await expect(
    page.getByRole("button", { name: "Revoke icon", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await expect(page.locator("#review")).not.toBeVisible();
});

test("pending → cancel unchanged → correction → repeat correction → reject; connection failure recovers", async ({
  page,
  request,
}) => {
  const name = "Correction " + randomUUID().slice(0, 8);
  const uploaded = await request.post("/v1/submissions", {
    headers: { "Idempotency-Key": randomUUID() },
    data: {
      applicationId: "org.appfaces.Correction",
      name,
      sourceUrl: "https://example.org/art",
      license: "CC0-1.0",
      variant: "default",
      iconBase64: icon(180),
    },
  });
  expect(uploaded.status()).toBe(201);
  const { id } = (await uploaded.json()) as { id: string };
  const state = async (status: string, version: number): Promise<void> => {
    const r = await request.get("/admin/submissions?status=" + status, {
      headers: { Authorization: "Bearer e2e-admin" },
    });
    const body = (await r.json()) as {
      submissions: { id: string; version: number }[];
    };
    expect(body.submissions.find((s) => s.id === id)?.version).toBe(version);
  };
  await login(page);
  await page.getByRole("button", { name: "Review " + name }).click();
  await page
    .getByRole("button", { name: "Request correction", exact: true })
    .click();
  await page.getByLabel("Decision reason").fill("Must not be saved.");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await state("pending", 0);
  for (const [i, reason] of [
    "Confirm license.",
    "Still awaiting evidence.",
  ].entries()) {
    if (i > 0) {
      await page.getByLabel("Contribution status").selectOption("correction");
      await page.getByRole("button", { name: "Review " + name }).click();
    }
    await page
      .getByRole("button", { name: "Request correction", exact: true })
      .click();
    await page.getByLabel("Decision reason").fill(reason);
    await page
      .getByRole("button", { name: "Confirm decision", exact: true })
      .click();
    await expect(page.locator("#decision")).not.toBeVisible();
    await expect(page.locator("#message")).toContainText("Decision saved");
    await state("correction", i + 1);
  }
  await page.getByRole("button", { name: "Review " + name }).click();
  await page
    .getByRole("button", { name: "Reject contribution", exact: true })
    .click();
  await page.getByLabel("Decision reason").fill("Permission not established.");
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  await expect(page.locator("#message")).toContainText("Decision saved");
  await state("rejected", 3);
  await page.route("**/admin/submissions?*", (route) => route.abort(), {
    times: 1,
  });
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(page.getByText("Could not load.")).toBeVisible();
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(page.getByText("Queue empty.")).toBeVisible();
});

test("accessible login and workspace at desktop and mobile sizes", async ({
  page,
}) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/admin");
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await page.getByLabel("Access password", { exact: true }).fill("incorrect");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.locator("#login-error")).toContainText(
      "Invalid password",
    );
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await login(page);
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
  }
});

test("moderator correction → receipt resubmission → stale review blocked → withdrawal visible", async ({
  page,
  request,
}) => {
  const name = "Receipt UI " + randomUUID().slice(0, 8);
  const metadata = {
    applicationId: "org.appfaces.ReceiptUi",
    name,
    sourceUrl: "https://example.org/art",
    license: "CC0-1.0",
    variant: "default",
  };
  const uploaded = await request.post("/v1/submissions", {
    headers: { "Idempotency-Key": randomUUID() },
    data: { ...metadata, iconBase64: icon(215) },
  });
  expect(uploaded.status()).toBe(201);
  const item = (await uploaded.json()) as { id: string; receipt: string };
  await login(page);
  await page.getByRole("button", { name: "Review " + name }).click();
  await page
    .getByRole("button", { name: "Request correction", exact: true })
    .click();
  await page.getByLabel("Decision reason").fill("Correct name and license.");
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  const receiptHeaders = {
    Authorization: "Receipt " + item.receipt,
    "Idempotency-Key": randomUUID(),
  };
  const status = await request.get(`/v1/submissions/${item.id}`, {
    headers: receiptHeaders,
  });
  expect(await status.json()).toMatchObject({
    status: "correction",
    version: 1,
    reason: "Correct name and license.",
  });
  const corrected = name + " corrigido";
  const correction = await request.post(
    `/v1/submissions/${item.id}/correction`,
    {
      headers: receiptHeaders,
      data: { version: 1, ...metadata, name: corrected },
    },
  );
  expect(correction.status()).toBe(200);
  await page.getByRole("button", { name: "Refresh data" }).click();
  await page.getByRole("button", { name: "Review " + corrected }).click();
  await page.getByRole("button", { name: "Approve icon", exact: true }).click();
  await page.getByLabel("Decision reason").fill("This review is stale.");
  const withdrawal = await request.post(`/v1/submissions/${item.id}/withdraw`, {
    headers: { ...receiptHeaders, "Idempotency-Key": randomUUID() },
    data: { version: 2 },
  });
  expect(withdrawal.status()).toBe(200);
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision-error")).toBeVisible();
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.keyboard.press("Escape");
  await page.getByLabel("Contribution status").selectOption("withdrawn");
  await page.getByRole("button", { name: "Review " + corrected }).click();
  await expect(
    page.getByRole("button", { name: "Revoke icon", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Approve icon", exact: true }),
  ).toHaveCount(0);
});

async function seedContribution(
  request: import("@playwright/test").APIRequestContext,
  name: string,
  color: number,
) {
  const applicationId = "org.appfaces.Flow" + randomUUID().replaceAll("-", "");
  const response = await request.post("/v1/submissions", {
    headers: { "Idempotency-Key": randomUUID() },
    data: {
      applicationId,
      name,
      sourceUrl: "https://example.org/art",
      license: "CC0-1.0",
      variant: "default",
      iconBase64: icon(color),
    },
  });
  expect(response.status()).toBe(201);
  return {
    ...((await response.json()) as { id: string; receipt: string }),
    applicationId,
  };
}
test("merge through UI validates target, preserves draft and publishes into existing application", async ({
  page,
  request,
}) => {
  const suffix = randomUUID().slice(0, 8),
    name = "Merge source " + suffix;
  const target = await seedContribution(request, "Merge target " + suffix, 221);
  const seed = await request.post(`/admin/submissions/${target.id}/decision`, {
    headers: { Authorization: "Bearer e2e-admin" },
    data: {
      action: "approve",
      version: 0,
      reason: "Seed existing merge target.",
    },
  });
  expect(seed.status()).toBe(200);
  const source = await seedContribution(request, name, 222);
  await login(page);
  await page.getByRole("button", { name: "Review " + name }).click();
  await page
    .getByRole("button", { name: "Merge into application", exact: true })
    .click();
  await page
    .getByLabel("Target application ID")
    .fill("org.appfaces.DoesNotExist");
  await page
    .getByLabel("Decision reason")
    .fill("Nova arte para o mesmo aplicativo.");
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision-error")).toContainText("must exist");
  await expect(page.getByLabel("Decision reason")).toHaveValue(
    "Nova arte para o mesmo aplicativo.",
  );
  await page.getByLabel("Target application ID").fill(target.applicationId);
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  const receipt = await request.get(`/v1/submissions/${source.id}`, {
    headers: { Authorization: "Receipt " + source.receipt },
  });
  expect(await receipt.json()).toMatchObject({ status: "merged", version: 1 });
  const catalog = (await (await request.get("/v1/catalog")).json()) as {
    applications: { id: string; name: string }[];
  };
  expect(
    catalog.applications.find((a) => a.id === target.applicationId)?.name,
  ).toBe(name);
  expect(catalog.applications.some((a) => a.id === source.applicationId)).toBe(
    false,
  );
  await page.getByRole("button", { name: "History", exact: true }).click();
  await expect(
    page.getByText("Nova arte para o mesmo aplicativo."),
  ).toBeVisible();
});

test("lost approval response retains draft; refresh reconciles committed state without duplicate write", async ({
  page,
  request,
}) => {
  const name = "Lost response " + randomUUID().slice(0, 8);
  const item = await seedContribution(request, name, 223);
  await login(page);
  await page.getByRole("button", { name: "Review " + name }).click();
  await page.getByRole("button", { name: "Approve icon", exact: true }).click();
  const reason = "Decision committed before connection loss.";
  await page.getByLabel("Decision reason").fill(reason);
  let writes = 0;
  page.on("request", (r) => {
    if (
      r.url().endsWith(`/admin/submissions/${item.id}/decision`) &&
      r.method() === "POST"
    )
      writes++;
  });
  await page.route(
    `**/admin/submissions/${item.id}/decision`,
    async (route) => {
      const committed = await route.fetch();
      expect(committed.status()).toBe(200);
      await route.abort("connectionfailed");
    },
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision-error")).toContainText(
    "Connection failed",
  );
  await expect(page.getByLabel("Decision reason")).toHaveValue(reason);
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Refresh data" }).click();
  await expect(
    page.getByRole("button", { name: "Review " + name }),
  ).toHaveCount(0);
  await page.getByLabel("Contribution status").selectOption("approved");
  await expect(
    page.getByRole("button", { name: "Review " + name }),
  ).toBeVisible();
  const status = await request.get(`/v1/submissions/${item.id}`, {
    headers: { Authorization: "Receipt " + item.receipt },
  });
  expect(await status.json()).toMatchObject({ status: "approved", version: 1 });
  const history = (await (
    await request.get("/admin/reviews", {
      headers: { Authorization: "Bearer e2e-admin" },
    })
  ).json()) as { submission_id: string; decision: string }[];
  expect(
    history.filter(
      (r) => r.submission_id === item.id && r.decision === "approve",
    ),
  ).toHaveLength(1);
  expect(writes).toBe(1);
});

test("expired access → failed reauthentication → renewed access restores draft without auto-submit", async ({
  page,
  request,
}) => {
  const name = "Reauthenticate " + randomUUID().slice(0, 8);
  const item = await seedContribution(request, name, 224);
  await login(page);
  await page.getByRole("button", { name: "Review " + name }).click();
  await page.getByRole("button", { name: "Approve icon", exact: true }).click();
  const reason = "Draft survives reauthentication.";
  await page.getByLabel("Decision reason").fill(reason);
  await page.route(
    `**/admin/submissions/${item.id}/decision`,
    (route) =>
      route.fulfill({
        status: 403,
        contentType: "application/json",
        body: JSON.stringify({ error: "Invalid moderator token" }),
      }),
    { times: 1 },
  );
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#login-error")).toContainText("draft is saved");
  await page.getByLabel("Access password", { exact: true }).fill("incorrect");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#login-error")).toContainText("Invalid password");
  await page.getByLabel("Access password", { exact: true }).fill("e2e-admin");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator("#decision")).toBeVisible();
  await expect(page.getByLabel("Decision reason")).toHaveValue(reason);
  const before = await request.get(`/v1/submissions/${item.id}`, {
    headers: { Authorization: "Receipt " + item.receipt },
  });
  expect(await before.json()).toMatchObject({ status: "pending", version: 0 });
  expect(
    await page.evaluate(() => ({
      local: localStorage.length,
      session: sessionStorage.length,
    })),
  ).toEqual({ local: 0, session: 0 });
  await page
    .getByRole("button", { name: "Confirm decision", exact: true })
    .click();
  await expect(page.locator("#decision")).not.toBeVisible();
  const after = await request.get(`/v1/submissions/${item.id}`, {
    headers: { Authorization: "Receipt " + item.receipt },
  });
  expect(await after.json()).toMatchObject({ status: "approved", version: 1 });
});

const locales = ["en", "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur"];
for (const language of locales) {
  test(`localized review flow: ${language}`, async ({ browser, request }) => {
    const { readFile } = await import("node:fs/promises");
    const messages = JSON.parse(
      await readFile(
        new URL(`../../app_faces/locales/${language}.json`, import.meta.url),
        "utf8",
      ),
    ) as Record<string, string>;
    const text = (key: string): string => {
      const value = messages[key];
      if (!value) throw Error("Missing test translation: " + key);
      return value;
    };
    const name = `App <b>العربية বাংলা हिन्दी</b> ${randomUUID().slice(0, 8)}`;
    const response = await request.post("/v1/submissions", {
      headers: { "Idempotency-Key": randomUUID() },
      data: {
        applicationId: "org.appfaces.Locale" + language,
        name,
        sourceUrl: "https://example.org/icons",
        license: "CC0-1.0",
        variant: "default",
        iconBase64: icon(),
      },
    });
    expect(response.status()).toBe(201);
    const proposal = (await response.json()) as { id: string };
    const context = await browser.newContext({
      locale: language,
      viewport: { width: 390, height: 844 },
    });
    const page = await context.newPage();
    try {
      await page.goto("http://127.0.0.1:8791/admin");
      await expect(page.locator("html")).toHaveAttribute("lang", language);
      await expect(page.locator("html")).toHaveAttribute(
        "dir",
        ["ar", "ur"].includes(language) ? "rtl" : "ltr",
      );
      await expect(
        page.getByLabel(text("Access password"), { exact: true }),
      ).toBeVisible();
      await expect(page.getByRole("combobox")).toHaveCount(0);
      await page
        .getByLabel(text("Access password"), { exact: true })
        .fill("incorrect");
      await page
        .getByRole("button", { name: text("Sign in"), exact: false })
        .click();
      await expect(page.locator("#login-error")).toHaveText(
        text("Invalid password or expired access. Sign in again."),
      );
      await expect(page.locator("#token")).toHaveValue("incorrect");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page
        .getByLabel(text("Access password"), { exact: true })
        .fill("e2e-admin");
      await page
        .getByRole("button", { name: text("Sign in"), exact: false })
        .click();
      await expect(page.locator("#page-title")).toHaveText(
        text("Review queue"),
      );
      await page.getByRole("searchbox").fill(name);
      const reviewName = text("Review {name}").replace("{name}", name);
      await page.getByRole("button", { name: reviewName, exact: true }).click();
      await expect(page.locator("#review-title")).toHaveText(name);
      await expect(page.locator("#review-title b")).toHaveCount(0);
      await page
        .getByRole("button", { name: text("Request correction"), exact: true })
        .click();
      const reason = `Check license · العربية · বাংলা · हिन्दी · ${language}`;
      await page
        .getByLabel(text("Decision reason"), { exact: true })
        .fill(reason);
      await page
        .getByRole("button", { name: text("Cancel"), exact: true })
        .click();
      await expect(page.locator("#review")).toBeVisible();
      await page
        .getByRole("button", { name: text("Request correction"), exact: true })
        .click();
      await page
        .getByLabel(text("Decision reason"), { exact: true })
        .fill(reason);
      await page.screenshot({
        path: `../state/i18n-${language}.png`,
        fullPage: true,
      });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await page
        .getByRole("button", { name: text("Confirm decision"), exact: true })
        .click();
      await expect(page.locator("#decision")).not.toBeVisible();
      await expect(page.locator("#message")).toHaveText(
        text("Decision saved."),
      );
      const state = await request.get("/admin/submissions?status=correction", {
        headers: { Authorization: "Bearer e2e-admin" },
      });
      const rows = (await state.json()) as {
        submissions: Array<{
          id: string;
          name: string;
          status: string;
          reason: string;
        }>;
      };
      expect(
        rows.submissions.find((row) => row.id === proposal.id),
      ).toMatchObject({ name, reason, status: "correction" });
    } finally {
      await context.close();
    }
  });
}

test("unsupported browser language ignores an obsolete saved preference and falls back to English", async ({
  browser,
}) => {
  const context = await browser.newContext({ locale: "de-DE" });
  await context.addInitScript(() =>
    localStorage.setItem("app-faces.language", "ar"),
  );
  const page = await context.newPage();
  try {
    await page.goto("/admin");
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await expect(
      page.getByLabel("Access password", { exact: true }),
    ).toBeVisible();
    await expect(page.getByRole("combobox")).toHaveCount(0);
  } finally {
    await context.close();
  }
});

test("single login card stays centered and supports keyboard sign-in on narrow screens", async ({
  page,
}) => {
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 320, height: 568 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/admin");
    const card = await page.locator(".login-card").boundingBox();
    expect(card).not.toBeNull();
    expect(
      Math.abs(card!.x + card!.width / 2 - viewport.width / 2),
    ).toBeLessThanOrEqual(2);
    expect(
      Math.abs(card!.y + card!.height / 2 - viewport.height / 2),
    ).toBeLessThanOrEqual(2);
    expect(card!.x).toBeGreaterThanOrEqual(16);
    expect(card!.y).toBeGreaterThanOrEqual(16);
    expect(card!.x + card!.width).toBeLessThanOrEqual(viewport.width - 16);
    await expect(page.locator("#login-screen aside")).toHaveCount(0);
    await expect(page.getByRole("combobox")).toHaveCount(0);
  }
  const password = page.getByLabel("Access password", { exact: true });
  await password.fill("e2e-admin");
  await password.press("Tab");
  await expect(
    page.getByRole("button", { name: "Show password" }),
  ).toBeFocused();
  await page.keyboard.press("Space");
  await expect(password).toHaveAttribute("type", "text");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Sign in", exact: false }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#workspace")).toBeVisible();
});

test("review opened during icon download receives its preview without reopening", async ({
  page,
  request,
}) => {
  const name = "Delayed preview " + randomUUID().slice(0, 8);
  const item = await seedContribution(request, name, 225);
  let releaseDownload!: () => void;
  const downloadGate = new Promise<void>((resolve) => {
    releaseDownload = resolve;
  });
  await page.route(`**/admin/submissions/${item.id}/icon`, async (route) => {
    await downloadGate;
    await route.continue();
  });
  try {
    await login(page);
    await page.getByRole("searchbox").fill(name);
    await page.getByRole("button", { name: "Review " + name }).click();
    await expect(
      page.getByText("Preview unavailable", { exact: true }),
    ).toBeVisible();
    releaseDownload();
    const preview = page.getByRole("img", {
      name: "Submitted icon",
      exact: true,
    });
    await expect(preview).toBeVisible();
    await expect
      .poll(() =>
        preview.evaluate((image: HTMLImageElement) => image.naturalWidth),
      )
      .toBe(64);
    await expect(page.getByText("No icon", { exact: true })).toBeVisible();
    await expect(page.locator("#review-title")).toHaveText(name);
  } finally {
    releaseDownload();
  }
});

test("compact workspace supports narrow review, keyboard dismissal and all navigation destinations", async ({
  page,
  request,
}) => {
  const name = "Layout " + randomUUID().slice(0, 8);
  await seedContribution(request, name, 226);
  await login(page);
  await page.getByRole("searchbox").fill(name);
  await expect(page.locator(".icon-well img")).toBeVisible();
  for (const viewport of [
    { width: 1440, height: 1000 },
    { width: 320, height: 568 },
  ]) {
    await page.setViewportSize(viewport);
    await page.screenshot({
      path: `../state/admin-workspace-${viewport.width}.png`,
      fullPage: true,
    });
    const row = page.getByRole("button", { name: "Review " + name });
    await row.click();
    const dialog = page.locator("#review");
    const bounds = await dialog.boundingBox();
    expect(bounds).not.toBeNull();
    expect(
      Math.abs(bounds!.x + bounds!.width / 2 - viewport.width / 2),
    ).toBeLessThanOrEqual(2);
    expect(
      await dialog.evaluate(
        (element) => element.scrollWidth <= element.clientWidth,
      ),
    ).toBe(true);
    const approve = page.getByRole("button", {
      name: "Approve icon",
      exact: true,
    });
    await expect(approve).toBeInViewport();
    const accessibility = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(accessibility.violations).toEqual([]);
    await page.screenshot({
      path: `../state/admin-review-${viewport.width}.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "Approve icon", exact: true })
      .click();
    await page.getByLabel("Decision reason").fill("Unsubmitted layout review.");
    expect(
      (
        await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze()
      ).violations,
    ).toEqual([]);
    await expect(
      page.getByRole("button", { name: "Confirm decision", exact: true }),
    ).toBeInViewport();
    await page.screenshot({
      path: `../state/admin-decision-${viewport.width}.png`,
      fullPage: true,
    });
    expect(
      await page
        .locator("#decision")
        .evaluate((element) => element.scrollWidth <= element.clientWidth),
    ).toBe(true);
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Approve icon", exact: true }),
    ).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(row).toBeFocused();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
  for (const [destination, heading] of [
    ["History", "Decision history"],
    ["Catalog versions", "Catalog versions"],
    ["Review queue", "Review queue"],
  ] as const) {
    await page.getByRole("button", { name: destination, exact: true }).click();
    await expect(page.locator("#page-title")).toHaveText(heading);
    await expect(
      page.getByRole("button", { name: destination, exact: true }),
    ).toHaveAttribute("aria-current", "page");
    await expect(page.locator("#refresh")).toBeEnabled();
    await page.screenshot({
      path: `../state/admin-${destination.replaceAll(" ", "-").toLowerCase()}-320.png`,
      fullPage: true,
    });
  }
  await page.getByRole("button", { name: "Sign out", exact: false }).click();
  await expect(page.locator("#login-screen")).toBeVisible();
});
