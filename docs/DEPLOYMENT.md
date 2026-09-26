# Cloudflare production deployment

deployed 2026-09-25 America/Sao_Paulo (2026-09-26 UTC).

- API: https://app-faces-catalog.lynxnathan.workers.dev
- Approval UI: https://app-faces-catalog.lynxnathan.workers.dev/admin
- Worker: `app-faces-catalog`
- Version: `3429749f-85b9-4c2c-abd0-ee3eb2f9b957`
- D1: `app-faces`, ID `d603a056-0722-4bbb-a4d6-83d6cae3ce99`
- Applied migrations: `0001_catalog.sql`, `0002_artwork.sql`, `0003_receipt_lifecycle.sql`.
- Backend bindings: D1, built-in rate limiter and two secrets. **No R2**.

## Free plan

Nathan confirmed Workers Free. Cloudflare independently confirmed it by rejecting
custom CPU limits with code100328 (“CPU limits are not supported for the Free
plan”). Custom override removed; the platform's fixed Free quota applies.
The account subscription endpoint was403 with the Wrangler OAuth scope; this is
not interpreted as either a paid plan or an absent subscription.

D1 contains normalized PNG BLOBs and metadata, so exceeding Free storage/query
limits fails operations rather than generating R2 overages. The fixed free limits
are account-wide (D1 has a500MB per-database limit); availability is bounded by them.
No plan upgrade is authorized. Sources:
https://developers.cloudflare.com/workers/platform/limits/
https://developers.cloudflare.com/d1/platform/limits/
https://developers.cloudflare.com/d1/platform/pricing/

## Authentication and local client

HTTPS moderation uses Bearer tokens, with roles checked on every admin API call.
Nathan's admin token is in `~/.config/app-faces/moderator-token` (mode0600).
Full deployment secrets are in `~/.config/app-faces/cloudflare-secrets.json`
(mode0600). Neither is stored in the repository or printed in verification logs.
Paste the token into the approval page; it stays in tab memory.
Contributors do not authenticate. No actual user icon was uploaded in testing.

The installed client now has the production `community_url` configured. Its prior
configuration is preserved in `~/.config/app-faces/config.before-cloudflare-deploy.json`.
This enables the optional contribution checkbox; it remains unchecked by default.
The first synced public catalog is empty after synthetic fixtures were revoked.

Wrangler authentication was already valid in the user's encrypted config/keyring.
An obsolete `~/.wrangler` cache directory shadowed `~/.config/.wrangler`.
It was preserved as `~/.wrangler-legacy-backup-1790390446`; nothing was deleted.
Future commands must run in lynxnathan's real desktop environment/keyring session.

## Verification

- Strict TypeScript +16 real workerd/D1 integration tests; nine Firefox scenarios.
- Python: 114 passed; two GTK checks passed separately with a graphical display.
- Integrated real Files/GTK → production Firefox approval → background sync →
  second native consumer → Undo/revocation: nine checks passed in isolated Xvfb;
  result (`state/native-e2e/result.json`, local). Synthetic fixtures, no app execution.
- Production client integration (`state/production-integration.json`, local): consent,
  private pending upload, approval, receipt, catalog/digest-verified fetch,
  revocation, revoked asset404.
- Production smoke (`state/production-smoke.json`, local): HTTPS page200, unauthorized
  admin401, admin token accepted,512×512 and261,433-byte PNGs uploaded successfully.
  Boundary proposals were rejected immediately; synthetic approved artwork revoked.
  Wall times are recorded, not misrepresented as CPU measurements.

## Update and rollback

Run the backend build/checks, apply new D1 migrations, and deploy with Wrangler as
the authenticated desktop user. Existing secrets must be preserved. Reversible
catalog decisions use the approval dashboard's revoke/rollback. Code rollback uses
Cloudflare version history once more than one successful version exists.

Desktop `app-faces uninstall` affects the client only. It does not delete hosted
resources. For a separately requested backend uninstall, export this D1 database
(including icons), then remove only the named Worker/database. No resource deletion
or paid resource activation is part of this deployment.

## Initial moderation redesign — 2026-09-26

The redesigned web interface was deployed as version
`b109d4ba-d400-44a7-8961-b92a422ae57b` on the same Worker, D1 database and free plan.
The bundle was 53.36 KiB, or 15.85 KiB gzip.

The interface added password login, queue/history/version navigation, search,
side-panel review, decision confirmation with error recovery, and desktop/mobile
layouts. Passwords remain in tab memory. Backend authorization remains authoritative.

That deployment passed 12 backend tests, four strict TypeScript configurations,
five Firefox scenarios including axe WCAG A/AA, and formatting checks. See
[moderation flows](MODERATION-FLOWS.md) for current coverage. The deployed-page
check was saved locally at `state/production-ui-smoke.json`.

## Lifecycle deployment — 26 September 2026

The Worker version was `3429749f-85b9-4c2c-abd0-ee3eb2f9b957`.
Migration 0003 adds withdrawn submission state and receipt-operation idempotency.
Pending/correction contributions can be corrected or withdrawn using their private
receipt; approved publication remains controlled by moderation. Six real-client
production checks passed in `state/production-receipt-lifecycle.json`.

Retention is **preserve**, with no automatic deletion job. An atomic admission
check limits stored artwork to 256 MiB; `/admin/storage` reports usage and status
counts to administrators. This ceiling leaves D1 metadata overhead room but does
not guarantee availability before every account-wide Free limit. The captured
usage snapshot is `state/production-storage.json`; it is not a live counter.

This update introduced no new billed service and no plan upgrade. Browser coverage
now comprises nine Firefox scenarios and the backend suite sixteen tests.


## Internationalization deployment — 26 September 2026

Worker version `208a508b-ad93-45e4-89a5-36c28ba24abe` adds ten interface languages,
persisted language selection and RTL layouts. The existing Worker, D1 database,
secrets and Free plan are unchanged. Bundle size: 291.59 KiB, 52.36 KiB gzip.

Validation: 16 backend tests, 20 local Firefox scenarios, four strict TypeScript
configurations and six read-only checks against the deployed dashboard. The live
checks cover login, queue, history, revisions, logout and browser errors; they do
not modify the catalog. Local evidence: `state/production-ui-smoke.json`.


## Centered login deployment — 26 September 2026

Worker version `db72d0f5-2b74-488f-8990-566a7d911564` replaces the split login with
one centered card. Browser language preferences select the locale automatically;
the selector and saved-language override are removed. Existing credentials and
D1 data are unchanged. Bundle: 287.46 KiB, 51.35 KiB gzip.

Validation: 16 Worker/D1 tests, 21 Firefox scenarios, strict TypeScript checks and
formatting. Browser checks include desktop/mobile centering, 320px keyboard login,
WCAG A/AA scans and all ten languages. Screenshots remain local.


## Moderation workspace deployment — 26 September 2026

Worker version `09bc9864-ae0d-4355-8d4b-ff2eb9c7b53d` replaces the moderation
sidebar with top navigation and centers the review dialog. Review and confirmation
actions remain visible while dialog content scrolls. Submitted previews update
when their download finishes, including reviews opened before image arrival.
Bundle: 287.50 KiB, 51.34 KiB gzip. Existing Worker/D1 bindings and Free plan remain
unchanged; this deployment needs no database migration.

Validation: 16 Worker/D1 cases, 23 Firefox scenarios, four strict TypeScript
configurations and formatting. After the final mobile button-spacing adjustment,
the responsive scenario and ten locale flows were rerun successfully. Browser
coverage includes delayed images, desktop/320px dialogs, keyboard focus recovery,
visible actions and automated accessibility checks.
Production login, authenticated queue, history, versions, logout and browser-error
checks also passed without catalog writes. Evidence remains local at
`state/production-ui-smoke.json`.


## Madame Sata theme deployment — 26 September 2026

Worker version `ed71c9a0-526e-492d-b5d7-5e7d25fac14d` applies the dark plum,
burgundy and gold theme throughout moderation. Headings use local serif fonts;
artwork previews use a light transparency grid. No external font or image requests
were added. Bundle: 288.86 KiB, 51.72 KiB gzip. Worker/D1 resources are unchanged.

Validation: 23 local Firefox scenarios, strict TypeScript and formatting passed.
Automated accessibility checks cover login, invalid-password feedback, queue,
review and confirmation. Desktop/mobile screenshots were inspected locally.
The six read-only production checks also passed: login, queue, history, versions,
logout and no uncaught browser errors. Local report:
`state/production-ui-smoke.json`.


## Minimal login deployment — 26 September 2026

Worker version `70f5646a-eb5d-42ca-9590-684b0a203cde` removes the visible login
name, heading and description. The mark, password label/input and sign-in action
remain. Password visibility uses an eye icon with localized accessible labels.
Errors remain conditional. Bundle: 289.05 KiB, 51.88 KiB gzip.

All 23 Firefox scenarios, strict TypeScript and formatting passed. Login centering,
keyboard access, password visibility, authentication recovery and ten languages
remain covered. Desktop/mobile captures were inspected locally.
Six read-only production checks passed after deployment, including authentication
and logout. Worker/D1 resources and credentials are unchanged.
