# Roadmap crosscheck — 26/09/2026, delivery update

original roadmap, current code, recorded test evidence and the current production deployment. Each result retains its actual boundary; the complete isolated native/cloud journey is now verified by its own nine-check record.

| Original milestone | Delivered and exercised | Remaining acceptance |
| --- | --- | --- |
| 0. Desktop integration | GVFS + Files script, reversible installer/launcher ownership, actual metadata lifecycle | Nine integrated native-flow checks passed on Xvfb; Godot Wayland/XWayland dock grouping now passed; broader apps remain open |
| 1. Local resolver | Precedence, XDG, ambiguous wrappers, theme, cached hash and bounded AppImage extraction | Broader portable-build diversity and confidence calibration |
| 2. Catalog | Versioned rollback, exact local OCCT seed with provenance/backup | OCCT support covers only user-identified bytes, not generic versions |
| 3. Files MVP | Background scan/cache, Apply/Undo, refreshed GTK experience | Native UI → production → second native consumer passed; personal-session behavior remains distinct |
| 4. App search / dock | Explicit launcher generation/reuse, safe quoting and owned removal | Godot real Wayland/XWayland grouping and removal passed; visual overview click/launch and removal passed; other apps remain |
| 5. Providers | selfh.st/Dashboard/community; upstream commit-pinned metadata and asset URLs; per-asset sources | Per-brand permission is not established by collection attribution; larger portable sample |
| 6. Contributions | Opt-in, anonymous receipts, retry/idempotency, correction resubmission and withdrawal for pending/correction states; six production lifecycle checks | Published-artwork changes remain moderated; integrated native upload/publication/consumption passed |
| 7. Cloudflare / moderation | Workers Free + D1, migration0003, sixteen backend tests, nine Firefox scenarios; preserve retention and 256 MiB artwork admission ceiling | Prolonged load/Free quota exhaustion and manual assistive-technology acceptance not covered |
| 8. KDE / distribution | Native CTest and live isolated Dolphin cancel/Apply/Undo with explicit Refresh; tested version matrix | Real Plasma shell/dock, different distributions and portable binary packaging not verified |

## Actual application coverage

The deterministic benchmark selects 24 installed desktop entries before resolution, keeps failures, and adds the real OCCT portable file. Results: **15 unique executable associations, 7 ambiguities, 2 unsupported wrappers**. Declared artwork exists for **23/24**, while resolved artwork is available for **14/24**. This separates identity from artwork and does not imply a population-wide success rate.

OCCT's original baseline is unknown. A subsequent user-local catalog seed recognizes the exact previously identified build, with local official-site favicon and rollback history. No hash/artwork upload or generic version claim was introduced. [Selection, provenance and evidence](APPLICATION-COVERAGE.md).

## Evidence boundaries

- Python: 144 passed; two GTK checks passed separately with a graphical display.
- Backend: sixteen Worker/D1 tests; nine real Firefox scenarios, [flow detail](MODERATION-FLOWS.md).
- Production receipt lifecycle: six client/API checks (`../state/production-receipt-lifecycle.json`, local).
- Production current version: `3429749f-85b9-4c2c-abd0-ee3eb2f9b957`, migration0003 applied; [deployment](DEPLOYMENT.md).
- Installed desktop/portable benchmark: baseline (`../state/application-coverage.json`, local), local-seed comparison (`../state/application-coverage-after-local-seed.json`, local).
- Real GVFS lifecycle: five checks (`../state/lifecycle-integration.json`, local).
- Dolphin real UI: result (`../state/dolphin-live-e2e.json`, local), [screenshots and exact fallback limitation](../adapters/kde/README.md).
- Full isolated Files → native chooser/file picker → Apply/Undo → opt-in upload →
  Firefox production approval → background catalog sync/verified download →
  second-file native search/Apply/Undo → browser revocation: **nine checks passed**.
  Result (`../state/native-e2e/result.json`, local). Real applications on Xvfb/private D-Bus,
  fixture-only artwork, no executable launch. Personal-session Godot dock acceptance is now separately recorded in [DOCK-E2E.md](DOCK-E2E.md).

The original roadmap remains historical. These changes close concrete implementation gaps without converting compile tests into UI evidence or treating a heuristic score of 0.90 as measured 90% accuracy. Production tests used synthetic artwork only.


## Real upstream-artwork regression added

The official Godot portable exposed two actionable failures: its versioned name
hid existing upstream suggestions in the native chooser; then correct metadata
failed to refresh the visible Files tile. Shared filename hints and a reversible
journaled refresh xattr corrected those paths. The actual Godot tile now updates
and restores after Undo without reload, from an initially empty artwork cache.
The misleading Telegram binary remains untouched by the background scan.
[Evidence and filesystem limits](PORTABLE-NEGATIVE-CASES.md),
result (`../state/native-e2e/upstream-result.json`, local). This local client change did
not require a new cloud deployment. Godot dock grouping subsequently passed in the personal session for both display drivers: [DOCK-E2E.md](DOCK-E2E.md).

## Personal-session dock acceptance

two-driver result (`../state/dock-e2e/result.json`, local). Real Godot 4.7.2
windows used their observed Wayland app ID / X11 WM_CLASS. Each case passed generic
baseline → managed launcher/search registration → two windows under one correct
dock actor → close/remove → reopen generic. Captures were inspected locally.
The binary was executed only in this separate dock flow with isolated test config
and dummy audio. Visible overview result, click-to-launch and removal also passed. Other applications remain open.

## Remaining implementation gaps closed

Telegram (`../state/native-e2e/telegram-selfhst/upstream-result.json`, local),
configured source (`../state/native-e2e/configured-selfhst-mirror/upstream-result.json`, local),
file lifecycle (`../state/file-lifecycle-e2e.json`, local). Telegram now passes cancel,
actual Files rendering and Undo with a spatial matcher that rejects wrong shapes.
Configurable GitHub upstreams preserve defaults, isolate source failures and retain
cached applied artwork; the real native flow also passes with a source added by TOML
under a new ID. GVFS file move/journal migration, Undo, replacement identity guards,
stale automatic-art cleanup and external-choice preservation pass with the real scanner.
[Configuration and adapter contract](UPSTREAMS.md).

Dolphin acceptance now includes actual Apply/Undo and cancellation, but preview
redraw requires Refresh/F5 on the tested KIO version. The native UI provides that
instruction. Result (`../state/dolphin-live-e2e.json`, local), [platform cause and test](../adapters/kde/README.md).
