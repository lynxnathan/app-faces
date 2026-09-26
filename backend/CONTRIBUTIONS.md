# Anonymous contribution lifecycle

The private receipt is a capability, not a contributor account. Keep it local and
never put it in URLs, telemetry, screenshots or public catalog metadata.

## Contract

`GET /v1/submissions/:id`, `Authorization: Receipt <receipt>`, returns
`{status, reason, version, applicationId, name, sourceUrl, license, variant}`.
Missing/incorrect receipt returns 404 without confirming existence.

`POST /v1/submissions/:id/correction` uses the same authorization and a random
`Idempotency-Key` (16–128 ASCII letters/digits/underscore/hyphen). Body:

```json
{"version":1,"applicationId":"org.example.App","name":"Example","sourceUrl":"https://example.org/art","license":"CC0-1.0","variant":"default"}
```

All five metadata fields are required. Only pending/correction submissions can
change. A correction returns to pending, clears the prior reason and increments
the version. The old moderation request remains in the audit. Artwork is
unchanged: replacement artwork needs a separate explicitly consented submission.

`POST /v1/submissions/:id/withdraw` uses the same headers and `{ "version": 2 }`.
Pending/correction become withdrawn. This is terminal; it does not delete audit
or private storage, and never revokes a shared/public icon. Published, merged,
rejected, revoked and withdrawn submissions cannot be edited by a receipt.
Publication removal remains an administrator decision.

Both mutations return `{status, reason, version}`. Stale version returns 409.
Retry an uncertain operation using the **same key and identical body**: the
original successful response is returned, even after later transitions. Its
version may therefore be older than current GET status. Reusing the key with a
different body/action returns 409. Authentication is checked on every retry.
Mutation and audit are one D1 batch with optimistic version gating; simultaneous
moderation and receipt changes cannot both win. Failed/new writes are throttled;
successful operation retries are served without consuming the limiter again.

Uploads also now return `version` alongside `id`, `receipt` and `status`.
Migration `0003_receipt_lifecycle.sql` adds withdrawn status and the private
idempotency operation table while preserving existing submissions.

## Capacity and retention

New artwork admission has an atomic 256 MiB ceiling, leaving headroom below the
D1 Free per-database limit for SQL metadata/indexes. Set `ARTWORK_BUDGET_BYTES`
only to lower it; values above the ceiling are clamped. Existing blobs and
identical upload retries remain available at capacity. New blobs return 503
with an explicit capacity message, without creating a submission.

`GET /admin/storage` requires an administrator bearer credential and provides
artwork bytes/count, submission counts and oldest timestamps by status, the
configured ceiling and `retention: "preserve"`. It is a read-only capacity report.
No automatic deletion, paid storage provisioning or subscription upgrade occurs.
This artwork ceiling is **not** a total database size quota: receipt operations,
review history and catalog revisions still grow. Their retention requires a
separate policy and measured deployment storage; hitting provider limits fails
requests instead of provisioning paid capacity. Withdrawn artwork is retained
privately and deduplicated, not purged invisibly.

## Flow evidence

Backend integration tests exercise pending → correction → resubmission →
withdrawal, replay after later transitions, invalid receipts/metadata, immutable
publication boundary, two identical concurrent retries and withdrawal racing
publication. They verify persisted versions, audit count, artwork digest and
catalog state. Capacity tests fill an isolated reduced budget, race new artwork,
then verify retries/dedup and access-controlled reporting.

Firefox scenario exercises moderator correction through the real UI, receipt
resubmission through the API, then receipt withdrawal while a real approval
dialog is open. Stale approval must fail without publication; withdrawn history
remains visible with no approval/revocation controls. This is a browser/backend
flow, not proof of the native contribution client (tested separately).
