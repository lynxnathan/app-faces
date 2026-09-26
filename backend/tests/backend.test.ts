import { Buffer } from "node:buffer";
import { beforeEach, afterEach, describe, test, expect } from "vitest";
import { Miniflare } from "miniflare";
import { build } from "esbuild";
import { readFile, readdir } from "node:fs/promises";
import { deflateSync } from "node:zlib";
import { createHash, randomUUID } from "node:crypto";
let mf: Miniflare;
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
function png(color = 255): Buffer {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(1);
  ihdr.writeUInt32BE(1, 4);
  ihdr[8] = 8;
  ihdr[9] = 6;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(Buffer.from([0, color, 0, 0, 255]))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}
const payload = (name = "Example", color = 255) => ({
  applicationId: "org.example." + name,
  name,
  sourceUrl: "https://example.org/icon",
  license: "CC0-1.0",
  variant: "official",
  iconBase64: Buffer.from(png(color)).toString("base64"),
});
function call(
  path: string,
  method = "GET",
  body?: unknown,
  token?: string,
  extra: Record<string, string> = {},
) {
  return mf.dispatchFetch("http://localhost" + path, {
    method,
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...extra,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
}
async function upload(
  name: string,
  color = 255,
  key = randomUUID(),
  ip = randomUUID(),
) {
  const r = await call(
    "/v1/submissions",
    "POST",
    payload(name, color),
    undefined,
    { "Idempotency-Key": key, "CF-Connecting-IP": ip },
  );
  expect(r.status).toBe(201);
  return (await r.json()) as { id: string; receipt: string; status: string };
}
async function decision(
  id: string,
  action: string,
  version = 0,
  extra: Record<string, unknown> = {},
  token = "admin",
) {
  return call(
    "/admin/submissions/" + id + "/decision",
    "POST",
    { action, reason: "Test review", version, ...extra },
    token,
  );
}
beforeEach(async () => {
  const built = await build({
    entryPoints: ["src/index.ts"],
    bundle: true,
    format: "esm",
    write: false,
    target: "es2023",
    loader: { ".txt": "text" },
  });
  mf = new Miniflare({
    workers: [
      {
        name: "app",
        modules: true,
        script: built.outputFiles[0]!.text,
        compatibilityDate: "2026-07-30",
        d1Databases: ["DB"],
        ratelimits: {
          UPLOAD_LIMIT: {
            namespace_id: "1001",
            simple: { limit: 10, period: 60 },
          },
        },
        bindings: {
          RECEIPT_SECRET: "test-secret-with-at-least-32-characters",
          REVIEWERS: JSON.stringify([
            { name: "Nathan", token: "admin", role: "admin" },
            { name: "Reviewer", token: "reviewer", role: "reviewer" },
          ]),
        },
      },
    ],
  });
  const db = await mf.getD1Database("DB");
  for (const file of (await readdir("migrations"))
    .filter((f) => f.endsWith(".sql"))
    .sort()) {
    const migration = await readFile("migrations/" + file, "utf8");
    for (const sql of migration.split(";").filter((s) => s.trim()))
      await db.prepare(sql).run();
  }
}, 30000);
afterEach(async () => {
  await mf?.dispose();
});
describe("real Worker + D1-only integration", () => {
  test("pending is private, idempotent receipt reveals only own status, approval publishes", async () => {
    const key = randomUUID(),
      one = await upload("First", 255, key);
    const repeat = await call(
      "/v1/submissions",
      "POST",
      payload("First"),
      undefined,
      { "Idempotency-Key": key, "CF-Connecting-IP": randomUUID() },
    );
    expect(repeat.status).toBe(200);
    expect(await repeat.json()).toEqual(one);
    const conflict = await call(
      "/v1/submissions",
      "POST",
      payload("Changed"),
      undefined,
      { "Idempotency-Key": key, "CF-Connecting-IP": randomUUID() },
    );
    expect(conflict.status).toBe(409);
    const sha = createHash("sha256").update(png()).digest("hex");
    expect((await call("/v1/assets/" + sha + ".png")).status).toBe(404);
    expect((await call("/admin/submissions")).status).toBe(401);
    expect((await call("/v1/submissions/" + one.id)).status).toBe(404);
    expect(
      (
        await call("/v1/submissions/" + one.id, "GET", undefined, undefined, {
          Authorization: "Receipt " + one.receipt,
        })
      ).status,
    ).toBe(200);
    expect((await decision(one.id, "approve")).status).toBe(200);
    const cat = (await (await call("/v1/catalog")).json()) as {
      applications: { id: string }[];
    };
    expect(cat.applications.some((a) => a.id === "org.example.First")).toBe(
      true,
    );
    expect((await call("/v1/assets/" + sha + ".png")).status).toBe(200);
  });
  test("correction, merge, rejection and reviewer permissions", async () => {
    const target = await upload("MergeTarget", 41);
    expect((await decision(target.id, "approve")).status).toBe(200);
    const item = await upload("Merge", 42);
    expect((await decision(item.id, "correction")).status).toBe(200);
    const status = await (
      await call("/v1/submissions/" + item.id, "GET", undefined, undefined, {
        Authorization: "Receipt " + item.receipt,
      })
    ).json();
    expect(status).toMatchObject({
      status: "correction",
      reason: "Test review",
      version: 1,
    });
    expect(
      (
        await decision(item.id, "merge", 1, {
          targetApplicationId: "org.example.MergeTarget",
        })
      ).status,
    ).toBe(200);
    expect((await decision(item.id, "revoke", 2, {}, "reviewer")).status).toBe(
      403,
    );
    expect(
      (
        await call(
          "/admin/rollback",
          "POST",
          { revision: 1, reason: "test" },
          "reviewer",
        )
      ).status,
    ).toBe(403);
    const reject = await upload("Reject", 3);
    expect(
      (await decision(reject.id, "reject", 0, {}, "reviewer")).status,
    ).toBe(200);
    expect((await decision(reject.id, "approve", 1)).status).toBe(409);
  });
  test("concurrent reviewers cannot both win optimistic decision", async () => {
    const item = await upload("Race", 4);
    const results = await Promise.all([
      decision(item.id, "approve"),
      decision(item.id, "reject"),
    ]);
    expect(results.map((r) => r.status).sort()).toEqual([200, 409]);
    const db = await mf.getD1Database("DB");
    const rows = await db
      .prepare("SELECT count(*) AS n FROM reviews WHERE submission_id=?")
      .bind(item.id)
      .first<{ n: number }>();
    expect(rows?.n).toBe(1);
  });
  test("revocation survives historical catalogs and rollback", async () => {
    const item = await upload("Revoke", 7);
    await decision(item.id, "approve");
    const published = (await (await call("/v1/catalog")).json()) as {
      revision: number;
    };
    expect((await decision(item.id, "revoke", 1)).status).toBe(200);
    const sha = createHash("sha256").update(png(7)).digest("hex");
    expect((await call("/v1/assets/" + sha + ".png")).status).toBe(404);
    expect(
      (
        await call(
          "/admin/rollback",
          "POST",
          { revision: published.revision, reason: "restore" },
          "admin",
        )
      ).status,
    ).toBe(200);
    for (const path of [
      "/v1/catalog",
      "/v1/catalog?revision=" + published.revision,
    ]) {
      const c = (await (await call(path)).json()) as {
        applications: { id: string }[];
      };
      expect(c.applications.some((a) => a.id === "org.example.Revoke")).toBe(
        false,
      );
    }
    const repeat = await upload("RevokeAgain", 7);
    expect((await decision(repeat.id, "approve")).status).toBe(409);
  });
  test("restoring a prior revision creates a new revision and audit entry", async () => {
    const item = await upload("BeforeRollback", 19);
    expect((await decision(item.id, "approve")).status).toBe(200);
    const before = (await (await call("/v1/catalog")).json()) as {
      revision: number;
      applications: { id: string }[];
    };
    expect(before.applications.map((app) => app.id)).toEqual([
      "org.example.BeforeRollback",
    ]);
    await call(
      "/admin/rollback",
      "POST",
      { revision: 1, reason: "Return to empty baseline" },
      "admin",
    );
    const after = (await (await call("/v1/catalog")).json()) as {
      revision: number;
      applications: unknown[];
    };
    expect(after.revision).toBeGreaterThan(before.revision);
    expect(after.applications).toEqual([]);
    const audit = (await (
      await call("/admin/reviews", "GET", undefined, "admin")
    ).json()) as { decision: string }[];
    expect(audit[0]?.decision).toBe("rollback");
  });
  test("simultaneous uploads are throttled and their raw IP is absent from D1 rows", async () => {
    const ip = "192.0.2.94";
    const responses = await Promise.all(
      Array.from({ length: 15 }, (_, i) =>
        call(
          "/v1/submissions",
          "POST",
          payload("Throttle" + i, 30),
          undefined,
          { "Idempotency-Key": randomUUID(), "CF-Connecting-IP": ip },
        ),
      ),
    );
    expect(responses.filter((r) => r.status === 201)).toHaveLength(10);
    expect(responses.filter((r) => r.status === 429)).toHaveLength(5);
    const db = await mf.getD1Database("DB");
    const tables = await db
      .prepare("SELECT name FROM sqlite_master WHERE type='table'")
      .all<{ name: string }>();
    expect(tables.results.length).toBeGreaterThan(0);
    for (const { name } of tables.results.filter(
      ({ name }) => !name.startsWith("_cf_") && !name.startsWith("sqlite_"),
    )) {
      const quoted = '"' + name.replaceAll('"', '""') + '"';
      const rows = await db.prepare("SELECT * FROM " + quoted).all();
      expect(JSON.stringify(rows.results), name).not.toContain(ip);
    }
    const stored = await db
      .prepare(
        "SELECT count(*) AS n FROM submissions WHERE name LIKE 'Throttle%'",
      )
      .first<{ n: number }>();
    expect(stored?.n).toBe(10);
  });
  test("invalid/active formats, corrupt CRC and private metadata are rejected", async () => {
    const bad = png();
    bad[30] = (bad[30] ?? 0) ^ 1;
    for (const changes of [
      {
        iconBase64: Buffer.from('<svg onload="alert(1)"/>').toString("base64"),
      },
      { iconBase64: Buffer.from(bad).toString("base64") },
      { Exec: "/home/private/app" },
      { sourceUrl: "file:///etc/passwd" },
    ]) {
      const response = await call(
        "/v1/submissions",
        "POST",
        { ...payload("Invalid"), ...changes },
        undefined,
        { "Idempotency-Key": randomUUID(), "CF-Connecting-IP": randomUUID() },
      );
      expect(response.status).toBe(400);
    }
  });
  test("unknown provenance stays pending until reviewer resolves it", async () => {
    const r = await call(
      "/v1/submissions",
      "POST",
      {
        ...payload("Unknown"),
        sourceUrl: "",
        license: "Unknown — review required",
      },
      undefined,
      { "Idempotency-Key": randomUUID(), "CF-Connecting-IP": randomUUID() },
    );
    expect(r.status).toBe(201);
    const item = (await r.json()) as { id: string };
    expect((await decision(item.id, "approve")).status).toBe(400);
    expect(
      (
        await decision(item.id, "approve", 0, {
          sourceUrl: "https://example.org/license",
          license: "CC0-1.0",
        })
      ).status,
    ).toBe(200);
  });
  test("metadata is stripped and compressed pixel bombs are rejected", async () => {
    const image = png(88),
      extra = chunk("tEXt", Buffer.from("private path\0/home/secret"));
    const modified = Buffer.concat([
      image.subarray(0, 33),
      extra,
      image.subarray(33),
    ]);
    const response = await call(
      "/v1/submissions",
      "POST",
      { ...payload("Strip", 88), iconBase64: modified.toString("base64") },
      undefined,
      { "Idempotency-Key": randomUUID(), "CF-Connecting-IP": randomUUID() },
    );
    expect(response.status).toBe(201);
    const item = (await response.json()) as { id: string };
    const preview = await call(
      "/admin/submissions/" + item.id + "/icon",
      "GET",
      undefined,
      "admin",
    );
    expect(Buffer.from(await preview.arrayBuffer())).toEqual(image);
    const bomb = Buffer.concat([
      image.subarray(0, 33),
      chunk("IDAT", deflateSync(Buffer.alloc(2_000_000))),
      chunk("IEND", Buffer.alloc(0)),
    ]);
    const denied = await call(
      "/v1/submissions",
      "POST",
      { ...payload("Bomb"), iconBase64: bomb.toString("base64") },
      undefined,
      { "Idempotency-Key": randomUUID(), "CF-Connecting-IP": randomUUID() },
    );
    expect(denied.status).toBe(400);
  });
  test("dashboard shell is public but tokens and private queue never are", async () => {
    const response = await call("/admin");
    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Security-Policy")).toContain(
      "frame-ancestors 'none'",
    );
    expect(
      (await call("/admin/reviews", "GET", undefined, "wrong")).status,
    ).toBe(403);
    const content = await response.text();
    expect(content).not.toContain("test-secret");
    const privateItem = await upload(
      "PrivateDashboard" + randomUUID().replaceAll("-", ""),
    );
    for (const path of [
      "/admin/submissions",
      "/admin/reviews",
      `/admin/submissions/${privateItem.id}/icon`,
    ]) {
      expect((await call(path)).status, path).toBe(401);
      expect((await call(path, "GET", undefined, "wrong")).status, path).toBe(
        403,
      );
    }
    expect(content).not.toContain(privateItem.receipt);
    expect(content).not.toContain(privateItem.id);
  });
});

test("D1 artwork stores one private blob for duplicate uploads", async () => {
  const a = await upload("BlobStorageA", 73);
  const b = await upload("BlobStorageB", 73);
  const db = await mf.getD1Database("DB");
  const rows = await db
    .prepare(
      "SELECT count(*) AS total FROM artwork WHERE digest=(SELECT digest FROM submissions WHERE id=?)",
    )
    .bind(a.id)
    .first<{ total: number }>();
  expect(rows?.total).toBe(1);
  const preview = await call(
    `/admin/submissions/${b.id}/icon`,
    "GET",
    undefined,
    "admin",
  );
  expect(preview.status).toBe(200);
  expect(Buffer.from(await preview.arrayBuffer())).toEqual(png(73));
});

test("PNG validation handles maximum dimensions and near-limit compressed input", async () => {
  for (const height of [128, 512]) {
    const width = 512;
    const ihdr = Buffer.alloc(13);
    ihdr.writeUInt32BE(width);
    ihdr.writeUInt32BE(height, 4);
    ihdr[8] = 8;
    ihdr[9] = 6;
    const raw = Buffer.alloc((width * 4 + 1) * height);
    let state = 12345;
    for (let y = 0; y < height; y++) {
      for (let x = 1; x <= width * 4; x++) {
        state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
        raw[y * (width * 4 + 1) + x] =
          height === 128 && x % 4 !== 0 ? state >>> 24 : 255;
      }
    }
    const image = Buffer.concat([
      Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
      chunk("IHDR", ihdr),
      chunk("IDAT", deflateSync(raw)),
      chunk("IEND", Buffer.alloc(0)),
    ]);
    expect(image.length).toBeLessThanOrEqual(262144);
    const response = await call(
      "/v1/submissions",
      "POST",
      { ...payload("Boundary" + height), iconBase64: image.toString("base64") },
      undefined,
      { "Idempotency-Key": randomUUID(), "CF-Connecting-IP": randomUUID() },
    );
    expect(response.status).toBe(201);
  }
});

function receiptCall(
  item: { id: string; receipt: string },
  action: string,
  body: unknown,
  key = randomUUID(),
) {
  return call(`/v1/submissions/${item.id}/${action}`, "POST", body, undefined, {
    Authorization: "Receipt " + item.receipt,
    "Idempotency-Key": key,
    "CF-Connecting-IP": randomUUID(),
  });
}
const metadata = (name: string) => {
  const { iconBase64: _icon, ...fields } = payload(name);
  return fields;
};
test("receipt correction cycle preserves artwork, audit and retry response after later withdrawal", async () => {
  const item = await upload("Lifecycle", 201);
  await decision(item.id, "correction");
  const key = randomUUID(),
    body = { version: 1, ...metadata("LifecycleFixed") };
  const changed = await receiptCall(item, "correction", body, key);
  expect(changed.status).toBe(200);
  expect(await changed.json()).toEqual({
    status: "pending",
    reason: "",
    version: 2,
  });
  expect((await decision(item.id, "approve", 1)).status).toBe(409);
  const db = await mf.getD1Database("DB");
  const persisted = await db
    .prepare("SELECT name,digest FROM submissions WHERE id=?")
    .bind(item.id)
    .first<{ name: string; digest: string }>();
  expect(persisted?.name).toBe("LifecycleFixed");
  expect(persisted?.digest).toBe(
    createHash("sha256").update(png(201)).digest("hex"),
  );
  const withdrawn = await receiptCall(item, "withdraw", { version: 2 });
  expect(await withdrawn.json()).toEqual({
    status: "withdrawn",
    reason: "",
    version: 3,
  });
  const replay = await receiptCall(item, "correction", body, key);
  expect(await replay.json()).toEqual({
    status: "pending",
    reason: "",
    version: 2,
  });
  expect(
    (await receiptCall(item, "correction", { ...body, name: "Different" }, key))
      .status,
  ).toBe(409);
  expect(
    (await receiptCall(item, "correction", { ...body, version: 3 })).status,
  ).toBe(409);
  expect((await decision(item.id, "revoke", 3)).status).toBe(409);
  const history = await db
    .prepare("SELECT decision FROM reviews WHERE submission_id=? ORDER BY id")
    .bind(item.id)
    .all<{ decision: string }>();
  expect(history.results.map((r) => r.decision)).toEqual([
    "correction",
    "resubmit",
    "withdraw",
  ]);
});
test("receipt auth, metadata allowlist and terminal publication boundary", async () => {
  const item = await upload("ReceiptGuard", 202);
  for (const headers of [{}, { Authorization: "Receipt invalid" }]) {
    const privateStatus = await call(
      `/v1/submissions/${item.id}`,
      "GET",
      undefined,
      undefined,
      headers,
    );
    expect(privateStatus.status).toBe(404);
    expect(await privateStatus.json()).toEqual({
      error: "Submission not found",
    });
  }
  expect(
    (
      await receiptCall({ ...item, receipt: "wrong" }, "withdraw", {
        version: 0,
      })
    ).status,
  ).toBe(404);
  expect(
    (
      await receiptCall(item, "correction", {
        version: 0,
        ...metadata("No"),
        Exec: "/private",
      })
    ).status,
  ).toBe(400);
  expect((await receiptCall(item, "withdraw", { version: -1 })).status).toBe(
    400,
  );
  expect(
    (
      await receiptCall(item, "correction", {
        version: 0,
        ...metadata("No"),
        sourceUrl: "file:///tmp",
      })
    ).status,
  ).toBe(400);
  await decision(item.id, "approve");
  expect((await receiptCall(item, "withdraw", { version: 1 })).status).toBe(
    409,
  );
  expect(
    (await receiptCall(item, "correction", { version: 1, ...metadata("No") }))
      .status,
  ).toBe(409);
  expect(
    (
      await call(
        `/v1/assets/${createHash("sha256").update(png(202)).digest("hex")}.png`,
      )
    ).status,
  ).toBe(200);
});
test("concurrent withdrawal and publication have one winner; duplicate corrections apply once", async () => {
  const item = await upload("ReceiptRace", 203);
  const key = randomUUID(),
    body = { version: 0, ...metadata("ReceiptRaceFixed") };
  const same = await Promise.all([
    receiptCall(item, "correction", body, key),
    receiptCall(item, "correction", body, key),
  ]);
  expect(same.map((r) => r.status)).toEqual([200, 200]);
  const results = await Promise.all([
    receiptCall(item, "withdraw", { version: 1 }),
    decision(item.id, "approve", 1),
  ]);
  expect(results.map((r) => r.status).sort()).toEqual([200, 409]);
  const db = await mf.getD1Database("DB");
  const state = await db
    .prepare("SELECT status,version FROM submissions WHERE id=?")
    .bind(item.id)
    .first<{ status: string; version: number }>();
  expect(state?.version).toBe(2);
  const publicItem = await db
    .prepare("SELECT id FROM applications WHERE id=?")
    .bind("org.example.ReceiptRaceFixed")
    .first();
  expect(Boolean(publicItem)).toBe(state?.status === "approved");
  const history = await db
    .prepare("SELECT count(*) AS n FROM reviews WHERE submission_id=?")
    .bind(item.id)
    .first<{ n: number }>();
  expect(history?.n).toBe(2);
});

test("storage budget rejects new artwork atomically while existing uploads and private reports remain available", async () => {
  const built = await build({
    entryPoints: ["src/index.ts"],
    bundle: true,
    format: "esm",
    write: false,
    target: "es2023",
    loader: { ".txt": "text" },
  });
  const bounded = new Miniflare({
    modules: true,
    script: built.outputFiles[0]!.text,
    compatibilityDate: "2026-07-30",
    d1Databases: ["DB"],
    ratelimits: {
      UPLOAD_LIMIT: {
        namespace_id: "1002",
        simple: { limit: 100, period: 60 },
      },
    },
    bindings: {
      RECEIPT_SECRET: "test-secret-with-at-least-32-characters",
      REVIEWERS: JSON.stringify([
        { name: "Nathan", token: "admin", role: "admin" },
      ]),
      ARTWORK_BUDGET_BYTES: String(png(10).length),
    },
  });
  try {
    const db = await bounded.getD1Database("DB");
    let retained: unknown = null;
    for (const file of (await readdir("migrations"))
      .filter((f) => f.endsWith(".sql"))
      .sort()) {
      if (file === "0003_receipt_lifecycle.sql") {
        await db
          .prepare(
            "INSERT INTO submissions(id,receipt_hash,payload_hash,application_id,name,digest,source_url,license,variant,status,reason,version) VALUES ('migration_seed','private-receipt','original-payload','org.example.Before','Before','asset','https://example.org/source','CC0','default','correction','Preserve this reason',4)",
          )
          .run();
        await db
          .prepare(
            "INSERT INTO reviews(operation,submission_id,reviewer,decision,reason) VALUES ('old-review','migration_seed','Moderator','correction','Keep history')",
          )
          .run();
        retained = await db
          .prepare("SELECT * FROM submissions WHERE id='migration_seed'")
          .first();
      }
      for (const sql of (await readFile("migrations/" + file, "utf8"))
        .split(";")
        .filter((s) => s.trim()))
        await db.prepare(sql).run();
    }
    expect(
      await db
        .prepare("SELECT * FROM submissions WHERE id='migration_seed'")
        .first(),
    ).toEqual(retained);
    expect(
      await db
        .prepare("SELECT reason FROM reviews WHERE operation='old-review'")
        .first(),
    ).toEqual({ reason: "Keep history" });
    await db.prepare("DELETE FROM submissions WHERE id='migration_seed'").run();
    const key = randomUUID();
    const post = (name: string, color: number, k = key) =>
      bounded.dispatchFetch("http://localhost/v1/submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": k },
        body: JSON.stringify(payload(name, color)),
      });
    expect((await post("Stored", 10)).status).toBe(201);
    const replies = await Promise.all([
      post("FullA", 11, randomUUID()),
      post("FullB", 12, randomUUID()),
    ]);
    expect(replies.map((r) => r.status)).toEqual([503, 503]);
    expect((await post("Stored", 10)).status).toBe(200);
    expect((await post("SameArtwork", 10, randomUUID())).status).toBe(201);
    const report = await bounded.dispatchFetch(
      "http://localhost/admin/storage",
      { headers: { Authorization: "Bearer admin" } },
    );
    expect(await report.json()).toMatchObject({
      retention: "preserve",
      artwork: { count: 1, bytes: png(10).length },
    });
    expect(
      (await bounded.dispatchFetch("http://localhost/admin/storage")).status,
    ).toBe(401);
  } finally {
    await bounded.dispose();
  }
});
