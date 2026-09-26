const MAX_UPLOAD_BODY_BYTES = 370_000;
const MAX_METADATA_BODY_BYTES = 8_192;
const MAX_TEXT_LENGTH = 200;
const MAX_APPLICATION_ID_LENGTH = 160;
const MAX_SOURCE_URL_LENGTH = 2_048;
const MAX_LICENSE_LENGTH = 300;
const MAX_VARIANT_LENGTH = 100;
const MAX_REASON_LENGTH = 1_000;
const MAX_ACTION_LENGTH = 30;
const MAX_ICON_BASE64_LENGTH = 349_528;
const MAX_ARTWORK_STORAGE_BYTES = 268_435_456;
const UPLOAD_RETRY_SECONDS = 60;
const MIN_RECEIPT_SECRET_LENGTH = 32;
const SUBMISSION_ID_HEX_LENGTH = 32;
const MAX_QUERY_ROWS = 100;

import { normalizePng } from "./png";
import { dashboard } from "./ui";
export interface Env {
  DB: D1Database;
  UPLOAD_LIMIT: RateLimit;
  RECEIPT_SECRET: string;
  REVIEWERS: string;
  ARTWORK_BUDGET_BYTES?: string;
}
interface Reviewer {
  name: string;
  token: string;
  role: "admin" | "reviewer";
}
interface Submission {
  id: string;
  application_id: string;
  name: string;
  digest: string;
  source_url: string;
  license: string;
  variant: string;
  status: string;
  version: number;
  reason: string;
  receipt_hash: string;
  payload_hash: string;
}
interface Entry {
  id: string;
  name: string;
  digest: string;
  source_url: string;
  license: string;
  variant: string;
}
class HttpError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}
const json = (value: unknown, status = 200): Response =>
  Response.json(value, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
const digest = async (value: BufferSource | string): Promise<string> =>
  hex(
    await crypto.subtle.digest(
      "SHA-256",
      typeof value === "string" ? new TextEncoder().encode(value) : value,
    ),
  );
const hex = (value: ArrayBuffer): string =>
  [...new Uint8Array(value)]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
async function mac(secret: string, value: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return hex(
    await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)),
  );
}
async function boundedJson(
  request: Request,
  limit = MAX_UPLOAD_BODY_BYTES,
): Promise<Record<string, unknown>> {
  if (!request.headers.get("Content-Type")?.startsWith("application/json"))
    throw new HttpError(415, "Use application/json");
  const reader = request.body?.getReader();
  if (!reader) throw new HttpError(400, "Missing body");
  const parts: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const p = await reader.read();
    if (p.done) break;
    size += p.value.length;
    if (size > limit) {
      await reader.cancel();
      throw new HttpError(413, "Payload too large");
    }
    parts.push(p.value);
  }
  try {
    const raw = await new Blob(parts).text();
    const value: unknown = JSON.parse(raw);
    if (!value || typeof value !== "object" || Array.isArray(value))
      throw new Error();
    return value as Record<string, unknown>;
  } catch {
    throw new HttpError(400, "Invalid JSON object");
  }
}
function textField(
  value: unknown,
  name: string,
  max = MAX_TEXT_LENGTH,
): string {
  if (
    typeof value !== "string" ||
    !value.trim() ||
    value.length > max ||
    /[\x00-\x1f\x7f]/.test(value)
  )
    throw new HttpError(400, `Invalid ${name}`);
  return value.trim();
}
function appId(value: unknown): string {
  const v = textField(value, "applicationId", MAX_APPLICATION_ID_LENGTH);
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]*$/.test(v))
    throw new HttpError(400, "Invalid applicationId");
  return v;
}
function sourceField(value: unknown): string {
  if (value === "") return "";
  const text = textField(value, "sourceUrl", MAX_SOURCE_URL_LENGTH);
  let url: URL;
  try {
    url = new URL(text);
  } catch {
    throw new HttpError(400, "Invalid sourceUrl");
  }
  if (url.protocol !== "https:" || url.username || url.password)
    throw new HttpError(400, "Source must be HTTPS without credentials");
  return text;
}
async function reviewer(request: Request, env: Env): Promise<Reviewer> {
  const supplied = request.headers
    .get("Authorization")
    ?.replace(/^Bearer /, "");
  if (!supplied) throw new HttpError(401, "Moderator token required");
  const list = JSON.parse(env.REVIEWERS) as Reviewer[];
  const actual = await digest(supplied);
  for (const r of list) if ((await digest(r.token)) === actual) return r;
  throw new HttpError(403, "Invalid moderator token");
}
const snapshot = `INSERT INTO revisions(manifest) SELECT COALESCE(json_group_array(json_object('id',id,'name',name,'digest',digest,'source_url',source_url,'license',license,'variant',variant)),'[]') FROM (SELECT * FROM applications ORDER BY id)`;
async function catalog(request: Request, env: Env): Promise<Response> {
  const revision = new URL(request.url).searchParams.get("revision");
  if (revision !== null && !/^\d+$/.test(revision))
    throw new HttpError(400, "Invalid revision");
  const row = await env.DB.prepare(
    revision
      ? "SELECT id,manifest FROM revisions WHERE id=?"
      : "SELECT id,manifest FROM revisions ORDER BY id DESC LIMIT 1",
  )
    .bind(...(revision ? [Number(revision)] : []))
    .first<{ id: number; manifest: string }>();
  if (!row) throw new HttpError(404, "Revision not found");
  const bans = await env.DB.prepare("SELECT digest FROM revoked_assets").all<{
    digest: string;
  }>();
  const denied = new Set(bans.results.map((x) => x.digest));
  const entries = JSON.parse(row.manifest) as Entry[];
  return json({
    schemaVersion: 1,
    revision: row.id,
    applications: entries
      .filter((e) => !denied.has(e.digest))
      .map((e) => ({
        id: e.id,
        name: e.name,
        sha256: e.digest,
        iconUrl: new URL(`/v1/assets/${e.digest}.png`, request.url).href,
        sourceUrl: e.source_url,
        license: e.license,
        variant: e.variant,
      })),
  });
}
function artworkBudget(env: Env): number {
  const configuredBudget = Number(
    env.ARTWORK_BUDGET_BYTES ?? MAX_ARTWORK_STORAGE_BYTES,
  );
  return Number.isSafeInteger(configuredBudget) && configuredBudget > 0
    ? Math.min(configuredBudget, MAX_ARTWORK_STORAGE_BYTES)
    : MAX_ARTWORK_STORAGE_BYTES;
}
async function submit(request: Request, env: Env): Promise<Response> {
  const { success } = await env.UPLOAD_LIMIT.limit({
    key: request.headers.get("CF-Connecting-IP") ?? "local",
  });
  if (!success)
    return new Response(
      '{"error":"Upload limit reached; retry in 60 seconds"}',
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(UPLOAD_RETRY_SECONDS),
          "Cache-Control": "no-store",
        },
      },
    );
  if (
    !env.RECEIPT_SECRET ||
    env.RECEIPT_SECRET.length < MIN_RECEIPT_SECRET_LENGTH
  )
    throw new HttpError(503, "Submission service not configured");
  const key = request.headers.get("Idempotency-Key");
  if (!key || !/^[a-zA-Z0-9_-]{16,128}$/.test(key))
    throw new HttpError(
      400,
      "Provide a random Idempotency-Key (16–128 characters)",
    );
  const body = await boundedJson(request);
  const allowed = [
    "applicationId",
    "name",
    "sourceUrl",
    "license",
    "variant",
    "iconBase64",
  ];
  if (Object.keys(body).some((k) => !allowed.includes(k)))
    throw new HttpError(400, "Unknown metadata field");
  const applicationId = appId(body["applicationId"]),
    name = textField(body["name"], "name");
  const sourceUrl = sourceField(body["sourceUrl"]),
    license = textField(body["license"], "license", MAX_LICENSE_LENGTH),
    variant = textField(body["variant"], "variant", MAX_VARIANT_LENGTH);
  const base64 = textField(
    body["iconBase64"],
    "iconBase64",
    MAX_ICON_BASE64_LENGTH,
  );
  let png: Uint8Array;
  try {
    png = await normalizePng(
      Uint8Array.from(atob(base64), (c) => c.charCodeAt(0)),
    );
  } catch (e) {
    throw new HttpError(400, e instanceof Error ? e.message : "Invalid PNG");
  }
  const assetDigest = await digest(png),
    payloadHash = await digest(
      JSON.stringify([
        applicationId,
        name,
        sourceUrl,
        license,
        variant,
        assetDigest,
      ]),
    );
  const id = (await mac(env.RECEIPT_SECRET, "id:" + key)).slice(
      0,
      SUBMISSION_ID_HEX_LENGTH,
    ),
    receipt = await mac(env.RECEIPT_SECRET, "receipt:" + key);
  const existing = await env.DB.prepare(
    "SELECT payload_hash,status,version FROM submissions WHERE id=?",
  )
    .bind(id)
    .first<{ payload_hash: string; status: string; version: number }>();
  if (existing) {
    if (existing.payload_hash !== payloadHash)
      throw new HttpError(
        409,
        "Idempotency-Key already used for different content",
      );
    return json(
      { id, receipt, status: existing.status, version: existing.version },
      200,
    );
  }

  const budget = artworkBudget(env);

  await env.DB.prepare(
    "INSERT OR IGNORE INTO artwork(digest,png) SELECT ?,? WHERE (SELECT COALESCE(SUM(length(png)),0) FROM artwork)+? <= ?",
  )
    .bind(assetDigest, png.slice().buffer, png.length, budget)
    .run();
  if (
    !(await env.DB.prepare("SELECT digest FROM artwork WHERE digest=?")
      .bind(assetDigest)
      .first())
  )
    throw new HttpError(
      503,
      "Artwork storage is full; existing contributions remain available. Try again after capacity review.",
    );
  await env.DB.prepare(
    "INSERT OR IGNORE INTO submissions(id,receipt_hash,payload_hash,application_id,name,digest,source_url,license,variant) VALUES (?,?,?,?,?,?,?,?,?)",
  )
    .bind(
      id,
      await digest(receipt),
      payloadHash,
      applicationId,
      name,
      assetDigest,
      sourceUrl,
      license,
      variant,
    )
    .run();
  const written = await env.DB.prepare(
    "SELECT payload_hash,status,version FROM submissions WHERE id=?",
  )
    .bind(id)
    .first<{ payload_hash: string; status: string; version: number }>();
  if (written?.payload_hash !== payloadHash)
    throw new HttpError(409, "Concurrent idempotency conflict");
  return json(
    { id, receipt, status: written.status, version: written.version },
    201,
  );
}
async function receiptMutation(
  request: Request,
  env: Env,
  id: string,
  action: string,
): Promise<Response> {
  const receipt =
    request.headers.get("Authorization")?.replace(/^Receipt /, "") ?? "";
  const row = await env.DB.prepare(
    "SELECT * FROM submissions WHERE id=? AND receipt_hash=?",
  )
    .bind(id, await digest(receipt))
    .first<Submission>();
  if (!row) throw new HttpError(404, "Submission not found");
  const key = request.headers.get("Idempotency-Key");
  if (!key || !/^[a-zA-Z0-9_-]{16,128}$/.test(key))
    throw new HttpError(
      400,
      "Provide a random Idempotency-Key (16–128 characters)",
    );
  const body = await boundedJson(request, MAX_METADATA_BODY_BYTES);
  const fields =
    action === "correction"
      ? ["version", "applicationId", "name", "sourceUrl", "license", "variant"]
      : ["version"];
  if (Object.keys(body).some((k) => !fields.includes(k)))
    throw new HttpError(400, "Unknown metadata field");
  const version = body["version"];
  if (
    typeof version !== "number" ||
    !Number.isSafeInteger(version) ||
    version < 0
  )
    throw new HttpError(400, "Invalid version");
  const metadata =
    action === "correction"
      ? {
          applicationId: appId(body["applicationId"]),
          name: textField(body["name"], "name"),
          sourceUrl: sourceField(body["sourceUrl"]),
          license: textField(body["license"], "license", MAX_LICENSE_LENGTH),
          variant: textField(body["variant"], "variant", MAX_VARIANT_LENGTH),
        }
      : null;
  const keyHash = await digest(key),
    payloadHash = await digest(JSON.stringify([action, version, metadata]));
  const previous = async (): Promise<Response | null> => {
    const operation = await env.DB.prepare(
      "SELECT payload_hash,response FROM receipt_operations WHERE submission_id=? AND key_hash=?",
    )
      .bind(id, keyHash)
      .first<{ payload_hash: string; response: string }>();
    if (!operation) return null;
    if (operation.payload_hash !== payloadHash)
      throw new HttpError(
        409,
        "Idempotency-Key already used for different content",
      );
    return json(JSON.parse(operation.response) as unknown);
  };
  const repeated = await previous();
  if (repeated) return repeated;
  if (version !== row.version)
    throw new HttpError(409, "Submission changed; refresh first");
  if (!["pending", "correction"].includes(row.status))
    throw new HttpError(
      409,
      "Only pending contributions can be changed or withdrawn; published artwork requires moderator review",
    );
  const { success } = await env.UPLOAD_LIMIT.limit({
    key: request.headers.get("CF-Connecting-IP") ?? "local",
  });
  if (!success)
    return new Response(
      JSON.stringify({ error: "Upload limit reached; retry in 60 seconds" }),
      {
        status: 429,
        headers: {
          "Content-Type": "application/json",
          "Retry-After": String(UPLOAD_RETRY_SECONDS),
          "Cache-Control": "no-store",
        },
      },
    );
  const operation = crypto.randomUUID(),
    gate = "EXISTS (SELECT 1 FROM receipt_operations WHERE operation=?)";
  const result = {
    status: action === "withdraw" ? "withdrawn" : "pending",
    reason: "",
    version: version + 1,
  };
  const statements = [
    env.DB.prepare(
      "INSERT OR IGNORE INTO receipt_operations(operation,submission_id,key_hash,payload_hash,response) SELECT ?,?,?,?,? FROM submissions WHERE id=? AND version=? AND status IN ('pending','correction')",
    ).bind(
      operation,
      id,
      keyHash,
      payloadHash,
      JSON.stringify(result),
      id,
      version,
    ),
    env.DB.prepare(
      `INSERT INTO reviews(operation,submission_id,reviewer,decision,reason,previous_status) SELECT ?,?,'Receipt holder',?,'',status FROM submissions WHERE id=? AND ${gate}`,
    ).bind(
      operation,
      id,
      action === "withdraw" ? "withdraw" : "resubmit",
      id,
      operation,
    ),
  ];
  if (metadata)
    statements.push(
      env.DB.prepare(
        `UPDATE submissions SET application_id=?,name=?,source_url=?,license=?,variant=? WHERE id=? AND ${gate}`,
      ).bind(
        metadata.applicationId,
        metadata.name,
        metadata.sourceUrl,
        metadata.license,
        metadata.variant,
        id,
        operation,
      ),
    );
  statements.push(
    env.DB.prepare(
      `UPDATE submissions SET status=?,reason='',version=version+1 WHERE id=? AND ${gate}`,
    ).bind(result.status, id, operation),
  );
  const written = await env.DB.batch(statements);
  if (written[0]?.meta.changes !== 1) {
    const retry = await previous();
    if (retry) return retry;
    throw new HttpError(409, "Submission changed; refresh first");
  }
  return json(result);
}
async function decision(
  request: Request,
  env: Env,
  r: Reviewer,
  id: string,
): Promise<Response> {
  const body = await boundedJson(request, MAX_METADATA_BODY_BYTES),
    action = textField(body["action"], "action", MAX_ACTION_LENGTH),
    reason = textField(body["reason"], "reason", MAX_REASON_LENGTH);
  if (!["approve", "reject", "merge", "correction", "revoke"].includes(action))
    throw new HttpError(400, "Unknown decision");
  if (action === "revoke" && r.role !== "admin")
    throw new HttpError(403, "Admin required for revocation");
  const row = await env.DB.prepare("SELECT * FROM submissions WHERE id=?")
    .bind(id)
    .first<Submission>();
  if (!row) throw new HttpError(404, "Submission not found");
  if (body["version"] !== row.version)
    throw new HttpError(409, "Review changed; refresh first");
  if (!["pending", "correction"].includes(row.status) && action !== "revoke")
    throw new HttpError(409, "Submission already reviewed");
  if (["revoked", "withdrawn"].includes(row.status))
    throw new HttpError(409, "Submission is closed");
  const target =
    action === "merge"
      ? appId(body["targetApplicationId"])
      : row.application_id;
  if (
    action === "merge" &&
    !(await env.DB.prepare("SELECT id FROM applications WHERE id=?")
      .bind(target)
      .first())
  )
    throw new HttpError(400, "Merge target must exist");
  if (
    ["approve", "merge"].includes(action) &&
    (await env.DB.prepare("SELECT digest FROM revoked_assets WHERE digest=?")
      .bind(row.digest)
      .first())
  )
    throw new HttpError(409, "Artwork revoked");
  const reviewedLicense =
    body["license"] === undefined
      ? row.license
      : textField(body["license"], "license", MAX_LICENSE_LENGTH);
  const reviewedSource =
    body["sourceUrl"] === undefined
      ? row.source_url
      : sourceField(body["sourceUrl"]);
  if (
    ["approve", "merge"].includes(action) &&
    (/^unknown/i.test(reviewedLicense) || !reviewedSource)
  )
    throw new HttpError(
      400,
      "Resolve source URL and redistribution permission before publication",
    );
  const status: Record<string, string> = {
    approve: "approved",
    reject: "rejected",
    merge: "merged",
    correction: "correction",
    revoke: "revoked",
  };
  const op = crypto.randomUUID(),
    gate = "EXISTS (SELECT 1 FROM reviews WHERE operation=?)";
  const statements = [
    env.DB.prepare(
      "INSERT INTO reviews(operation,submission_id,reviewer,decision,reason,previous_status) SELECT ?,?,?,?,?,status FROM submissions WHERE id=? AND version=?",
    ).bind(op, id, r.name, action, reason, id, row.version),
  ];
  if (["approve", "merge"].includes(action))
    statements.push(
      env.DB.prepare(
        `UPDATE submissions SET license=?,source_url=? WHERE id=? AND ${gate}`,
      ).bind(reviewedLicense, reviewedSource, id, op),
    );
  if (["approve", "merge"].includes(action))
    statements.push(
      env.DB.prepare(
        `INSERT INTO applications(id,name,digest,source_url,license,variant) SELECT ?,name,digest,source_url,license,variant FROM submissions WHERE id=? AND ${gate} ON CONFLICT(id) DO UPDATE SET name=excluded.name,digest=excluded.digest,source_url=excluded.source_url,license=excluded.license,variant=excluded.variant`,
      ).bind(target, id, op),
    );
  if (action === "revoke") {
    statements.push(
      env.DB.prepare(
        `INSERT OR IGNORE INTO revoked_assets(digest) SELECT digest FROM submissions WHERE id=? AND ${gate}`,
      ).bind(id, op),
    );
    statements.push(
      env.DB.prepare(
        `DELETE FROM applications WHERE digest=? AND ${gate}`,
      ).bind(row.digest, op),
    );
  }
  statements.push(
    env.DB.prepare(
      `UPDATE submissions SET status=?,reason=?,version=version+1 WHERE id=? AND ${gate}`,
    ).bind(status[action], reason, id, op),
  );
  statements.push(env.DB.prepare(snapshot));
  statements.push(
    env.DB.prepare(
      "UPDATE reviews SET revision=(SELECT MAX(id) FROM revisions) WHERE operation=?",
    ).bind(op),
  );
  const result = await env.DB.batch(statements);
  if (result[0]?.meta.changes !== 1)
    throw new HttpError(409, "Concurrent review; refresh first");
  return json({ status: status[action] });
}
async function route(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url),
    path = url.pathname;
  if (path === "/health" && request.method === "GET") return json({ ok: true });
  if (path === "/admin" && request.method === "GET")
    return new Response(dashboard, {
      headers: {
        "Content-Type": "text/html;charset=utf-8",
        "Cache-Control": "no-store",
        "Content-Security-Policy":
          "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
      },
    });
  if (path === "/v1/catalog" && request.method === "GET")
    return catalog(request, env);
  if (path === "/v1/submissions" && request.method === "POST")
    return submit(request, env);
  const mutation =
    /^\/v1\/submissions\/([a-f0-9]{32})\/(correction|withdraw)$/.exec(path);
  if (mutation && request.method === "POST")
    return receiptMutation(request, env, mutation[1] ?? "", mutation[2] ?? "");
  const status = /^\/v1\/submissions\/([a-f0-9]{32})$/.exec(path);
  if (status && request.method === "GET") {
    const receipt =
      request.headers.get("Authorization")?.replace(/^Receipt /, "") ?? "";
    const row = await env.DB.prepare(
      "SELECT status,reason,version,application_id AS applicationId,name,source_url AS sourceUrl,license,variant FROM submissions WHERE id=? AND receipt_hash=?",
    )
      .bind(status[1], await digest(receipt))
      .first();
    if (!row) throw new HttpError(404, "Submission not found");
    return json(row);
  }
  const asset = /^\/v1\/assets\/([a-f0-9]{64})\.png$/.exec(path);
  if (asset && request.method === "GET") {
    const allowed = await env.DB.prepare(
      "SELECT id FROM applications WHERE digest=? AND digest NOT IN (SELECT digest FROM revoked_assets) LIMIT 1",
    )
      .bind(asset[1])
      .first();
    if (!allowed) throw new HttpError(404, "Artwork not published");
    const object = await env.DB.prepare(
      "SELECT png FROM artwork WHERE digest=?",
    )
      .bind(asset[1] ?? "")
      .first<{ png: number[] }>();
    if (!object) throw new HttpError(404, "Artwork missing");

    return new Response(new Uint8Array(object.png), {
      headers: {
        "Content-Type": "image/png",
        "Cache-Control": "no-cache",
        ETag: `"${asset[1]}"`,
        "X-Content-Type-Options": "nosniff",
      },
    });
  }
  if (path.startsWith("/admin/")) {
    const r = await reviewer(request, env);
    if (path === "/admin/submissions" && request.method === "GET") {
      const state = url.searchParams.get("status") ?? "pending";
      const rows = await env.DB.prepare(
        "SELECT id,application_id,name,digest,source_url,license,variant,status,reason,version,created_at,(SELECT count(*) FROM submissions s WHERE s.digest=submissions.digest) AS duplicates,(SELECT digest FROM applications a WHERE a.id=submissions.application_id) AS existing_digest,(SELECT variant FROM applications a WHERE a.id=submissions.application_id) AS existing_variant FROM submissions WHERE status=? ORDER BY created_at LIMIT ?",
      )
        .bind(state, MAX_QUERY_ROWS)
        .all();
      return json({
        reviewer: { name: r.name, role: r.role },
        submissions: rows.results,
      });
    }
    if (path === "/admin/storage" && request.method === "GET") {
      if (r.role !== "admin")
        throw new HttpError(403, "Admin required for storage report");
      const artwork = await env.DB.prepare(
        "SELECT count(*) AS count,COALESCE(SUM(length(png)),0) AS bytes FROM artwork",
      ).first();
      const submissions = await env.DB.prepare(
        "SELECT status,count(*) AS count,min(created_at) AS oldest FROM submissions GROUP BY status",
      ).all();
      return json({
        artwork,
        submissions: submissions.results,
        retention: "preserve",
        artworkCeilingBytes: artworkBudget(env),
      });
    }
    if (path === "/admin/revisions" && request.method === "GET")
      return json(
        (
          await env.DB.prepare(
            "SELECT id,created_at FROM revisions ORDER BY id DESC LIMIT ?",
          )
            .bind(MAX_QUERY_ROWS)
            .all()
        ).results,
      );
    if (path === "/admin/reviews" && request.method === "GET")
      return json(
        (
          await env.DB.prepare(
            "SELECT reviews.*, submissions.name AS application_name, submissions.application_id FROM reviews LEFT JOIN submissions ON submissions.id=reviews.submission_id ORDER BY reviews.id DESC LIMIT ?",
          )
            .bind(MAX_QUERY_ROWS)
            .all()
        ).results,
      );
    const preview = /^\/admin\/submissions\/([a-f0-9]{32})\/icon$/.exec(path);
    if (preview && request.method === "GET") {
      const row = await env.DB.prepare(
        "SELECT digest FROM submissions WHERE id=?",
      )
        .bind(preview[1])
        .first<{ digest: string }>();
      const object = row
        ? await env.DB.prepare("SELECT png FROM artwork WHERE digest=?")
            .bind(row.digest)
            .first<{ png: number[] }>()
        : null;
      if (!object) throw new HttpError(404, "Icon not found");
      return new Response(new Uint8Array(object.png), {
        headers: {
          "Content-Type": "image/png",
          "Cache-Control": "no-store",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    const review = /^\/admin\/submissions\/([a-f0-9]{32})\/decision$/.exec(
      path,
    );
    if (review && request.method === "POST")
      return decision(request, env, r, review[1] ?? "");
    if (path === "/admin/rollback" && request.method === "POST") {
      if (r.role !== "admin")
        throw new HttpError(403, "Admin required for rollback");
      const body = await boundedJson(request, MAX_METADATA_BODY_BYTES),
        reason = textField(body["reason"], "reason", MAX_REASON_LENGTH);
      if (!Number.isSafeInteger(body["revision"]))
        throw new HttpError(400, "Invalid revision");
      const row = await env.DB.prepare(
        "SELECT manifest FROM revisions WHERE id=?",
      )
        .bind(body["revision"])
        .first<{ manifest: string }>();
      if (!row) throw new HttpError(404, "Revision not found");
      await env.DB.batch([
        env.DB.prepare("DELETE FROM applications"),
        env.DB.prepare(
          "INSERT INTO applications(id,name,digest,source_url,license,variant) SELECT json_extract(value,'$.id'),json_extract(value,'$.name'),json_extract(value,'$.digest'),json_extract(value,'$.source_url'),json_extract(value,'$.license'),json_extract(value,'$.variant') FROM json_each(?) WHERE json_extract(value,'$.digest') NOT IN (SELECT digest FROM revoked_assets)",
        ).bind(row.manifest),
        env.DB.prepare(snapshot),
        env.DB.prepare(
          "INSERT INTO reviews(operation,reviewer,decision,reason,revision) VALUES (?,?,'rollback',?,(SELECT MAX(id) FROM revisions))",
        ).bind(
          crypto.randomUUID(),
          r.name,
          `Revision ${String(body["revision"])}: ${reason}`,
        ),
      ]);
      return json({ ok: true });
    }
  }
  throw new HttpError(404, "Not found");
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    try {
      return await route(request, env);
    } catch (e) {
      if (e instanceof HttpError) return json({ error: e.message }, e.status);
      return json({ error: "Service unavailable" }, 503);
    }
  },
} satisfies ExportedHandler<Env>;
