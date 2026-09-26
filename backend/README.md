# App Faces community catalog

Cloudflare Worker, D1 metadata/revisions/private PNG artwork and a
small browser moderator dashboard. Anonymous contributors never authenticate.
Only reviewers use tokens. No uploader IDs, emails, IP columns, analytics or
raw desktop files are stored by the application.

## Run locally

Node 24+, npm, then from this directory:

```sh
npm ci
npm run init:local
npm run migrate:local
npm run dev
```

Open `http://localhost:8787/admin`. `init:local` creates `.dev.vars` with random
local moderator and receipt secrets, mode 0600, without printing their values.
It preserves an existing file. Read the moderator token from that local file
when unlocking the dashboard. The token stays in tab memory, never localStorage.
There is no development authentication bypass. No Cloudflare account is needed
for local D1 development. Stop the foreground server with Ctrl+C.

```sh
npm run check          # strict backend, browser and test TypeScript + real workerd tests
npm run format:check
npm run build
npx wrangler deploy --dry-run --outdir dist
```

Tests exercise real local Worker, D1 SQL migrations and rate-limit binding,
not mocked persistence. They cover concurrent review conflicts and upload
limits, metadata allowlists, malformed PNG, private receipts, all review actions,
role separation, catalog rollback and revocation.

## Desktop integration contract

`POST /v1/submissions`, JSON, maximum 370,000 bytes. Send a random
`Idempotency-Key` of 16–128 alphanumeric/underscore/hyphen characters and reuse it
for retries of the **same** payload. A UUID works. Different content under the
same key returns 409. All requests count against the upload limit.

```json
{
  "applicationId": "org.example.App",
  "name": "Example App",
  "sourceUrl": "https://example.org/artwork",
  "license": "CC-BY-4.0; attribution: Example Project",
  "variant": "official",
  "iconBase64": "<base64 PNG bytes>"
}
```

`sourceUrl` may be empty and license may say `Unknown — review required` in a
pending submission. Reviewers must resolve both before approval. Nonempty source
URLs must use HTTPS with no credentials. The service does not fetch those URLs.
Unknown fields (including paths, Exec, arguments, email, fingerprints) are rejected.
Names max 200 characters, application ID max 160 (`[A-Za-z0-9._-]`), source URL
2048, license 300, variant 100. No contribution is sent absent desktop consent.

Normalize icons to RGB/RGBA 8-bit, noninterlaced PNG, maximum 512×512 and 256KiB.
The Worker checks signature, chunk CRCs/order, dimensions, bounded decompression
and scanline filters; strips ancillary metadata; rejects SVG, APNG, palette,
grayscale and interlaced inputs. Hashes refer to normalized artwork, never an
executable. Identical artwork shares a D1 BLOB row; each proposed app association
still gets independent review.

Response: `{ "id": "...", "receipt": "...", "status": "pending", "version": 0 }` (201,
200 on retry). Store the receipt locally alongside the upload retry key.
`GET /v1/submissions/:id` with `Authorization: Receipt <receipt>` returns only
`{status,reason,version,applicationId,name,sourceUrl,license,variant}`.
Unknown/wrong receipt returns 404. Correction requests are feedback through this
endpoint. Use the receipt correction/withdrawal endpoints in the
[contribution protocol](CONTRIBUTIONS.md); retry an uncertain operation with its
original idempotency key.

`GET /v1/catalog` returns `{schemaVersion:1,revision,applications:[...]}`.
Each application has `id,name,sha256,iconUrl,sourceUrl,license,variant`.
`?revision=N` retrieves a historic snapshot, with revoked digests always filtered.
Clients must validate downloads against SHA-256, replace manifests atomically,
and remove revoked mappings on update. A new revision may intentionally remove
entries. Already downloaded copies cannot be remotely erased.

`GET /v1/assets/:sha256.png` serves only artwork currently in the approved catalog
and not revoked. The artwork table has no direct public endpoint. PNG blobs are content-addressed
and never overwritten with differing bytes. Responses require revalidation (`no-cache`), so browsers cannot retain a
long-lived immutable response after revocation. Old revision assets that are no
longer current return 404 until restored; this is intentional. The immutable
**bytes** are distinct from the revocable publication permission.

## Moderation

Open `/admin` and provide an assigned reviewer token. The dashboard lists the
selected queue (up to 100 oldest), proposed artwork, app ID, source, license,
variant, same-artwork submission count and status. Reviewers can approve, reject,
merge into an existing application (replacing that application's current artwork),
or request correction. Approval/merge lets the reviewer fill in source URL and
redistribution permission. Admins can revoke artwork and restore earlier
catalog revisions. Revocation blocks every association of the same digest,
including historical manifests and rollback. Rejected/correction submissions
remain private.

`REVIEWERS` is a JSON secret array:
`[{"name":"Nathan","token":"<random secret>","role":"admin"}]`.
Assign additional named `reviewer` tokens manually; these can review but cannot
revoke or rollback. Rotate/remove by replacing the secret; there is no API that
lets a contributor grant permissions. These names are **reviewer audit identity**,
not contributor identity.

All `/admin/*` APIs require `Authorization: Bearer <token>`:

- `GET /admin/submissions?status=pending` (also correction/approved/merged/rejected/revoked).
- `GET /admin/submissions/:id/icon` returns private PNG.
- `POST /admin/submissions/:id/decision` with `{action,version,reason}`;
  merge adds `targetApplicationId`; approve/merge may override `sourceUrl,license`.
- `GET /admin/reviews`, `GET /admin/revisions` return latest 100.
- `POST /admin/rollback` with `{revision,reason}` (admin only).

Decisions use optimistic version checks and a single D1 batch transaction for
review, application mapping, submission status and revision publication. A stale
review returns 409. A no-op losing race can create an identical extra catalog
revision, but cannot publish the losing decision. Every successful rollback makes
a new revision and audit entry; it does not rewrite history. No source URL or
proposal text becomes executable dashboard HTML.

## Deploy when ready

Production is deployed at https://app-faces-catalog.lynxnathan.workers.dev.
The account is Workers Free, confirmed by Nathan and by Cloudflare's deployment
API (code100328 rejects custom CPU limits on Free). Fixed platform limits apply;
there are no R2, paid image-transformation, KV or Durable Object bindings.
PNG blobs are <=256KiB, below D1's2MB row limit. D1 Free database size is500MB;
account storage/operation quotas are shared. Exhaustion causes errors, not paid
upgrades. See [deployment record](../docs/DEPLOYMENT.md).

`wrangler.jsonc` contains this project's actual D1 ID. For a different account,
create a separate DB with `wrangler d1 create app-faces` and replace that ID.
Use fresh production secrets; the workstation's existing secrets live in private
`~/.config/app-faces/cloudflare-secrets.json` (never committed). Preserve the
receipt secret across releases. Separate staging uses its own Worker, D1 and secrets.

```sh
npx wrangler d1 migrations apply DB --remote
npm run check
npm run build
npx wrangler deploy --secrets-file "$HOME/.config/app-faces/cloudflare-secrets.json"
```

After deployment, verify unauthorized admin access, pending asset 404, upload,
receipt, moderation and catalog fetch before configuring clients. The sample
rate limit is 10 requests per 60 seconds, keyed by Cloudflare's connection IP.
Cloudflare's binding is location-local and deliberately approximate globally;
it is throttling, not a billing/spend guarantee. IP is not written to D1 or
application logs. Cloudflare infrastructure still necessarily handles transport
metadata. Worker observability is disabled in config. Retention/pruning policy
for old private submissions is not yet automated; administrative resource cleanup
is explicit.

Cloudflare account login and deployment belong to the operator. This project
never reads unrelated app credentials. Wrangler manages its own OAuth refresh.

## Teardown / recovery

Stop local dev and remove only this directory's ignored `.wrangler` state to reset
local data. Preserve `.dev.vars` if receipts should remain reusable. Production:
export D1 (including artwork) before destructive cleanup; remove only
the `app-faces-catalog` Worker and `app-faces` D1 database created for this project. Do not delete shared resources. For a bad
catalog decision, use dashboard rollback/revoke; for a bad code deployment, use
Cloudflare Worker deployment rollback. These solve different problems.

## Dependency/source notes

versions resolved from npm on 2026-09-25 and pinned in package-lock.
Wrangler 4.141.0 currently bundles Miniflare 5.20260925.0-alpha itself. The direct
test dependency uses latest stable Miniflare 4.20260730.0, with narrowly scoped
sharp 0.35.4 / undici 7.29.0 security overrides. This keeps stable test APIs while
avoiding the older transitive versions' published vulnerabilities. Tests use that
runtime's supported compatibility date; actual Wrangler dry-run uses 2026-09-25.
Production Worker has no external runtime JS dependencies.

Official references used:

- https://developers.cloudflare.com/workers/testing/
- https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/
- https://developers.cloudflare.com/workers/local-development/bindings-per-env/
- https://developers.cloudflare.com/d1/worker-api/d1-database/
- https://developers.cloudflare.com/r2/api/workers/workers-api-reference/

## Free-only deployment requirement

Nathan requires zero cost. R2 was removed before production. Workers and
D1 operate on the verified Free account; platform quotas reject excess operations.
Do not upgrade this account or add paid services as an automatic recovery action.
The normalizer was optimized to avoid bit-by-bit CRC and per-byte scanline checks;
production accepted a512×512 PNG and a261,433-byte PNG under the fixed Free quota.
These are observed boundary samples, not a benchmark of all possible inputs.

Official quotas: https://developers.cloudflare.com/workers/platform/limits/
and https://developers.cloudflare.com/d1/platform/limits/.
