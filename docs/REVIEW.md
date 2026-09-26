# First-pass review — App Faces

local implementation and verification records from 2026-09-25/26;
roadmap crosschecked against source and evidence on 2026-09-26.

## Product review

The installed Files action opens the native chooser. Automatic matching runs from
`app-faces.timer`; no Load button is needed. Try a portable application with a known
.desktop entry or embedded AppImage icon, then test a plain unknown binary. The
former can acquire artwork automatically; the latter remains a user choice.

Choose an image and Apply; delete/move the source image and the applied icon still
works because App Faces keeps an immutable normalized local copy. Undo restores the
previous metadata and remembers the user's opt-out. Change the icon externally,
then undo: App Faces must preserve that later choice.

Add to applications is explicit. Existing launchers are reused. New generated
entries do not promise correct dock grouping unless the application's actual
Wayland app ID/WM class is supplied/known.

```sh
app-faces pause
app-faces resume
app-faces rollback
app-faces uninstall
```

Rollback pauses automation and restores owned icons/launchers. Uninstall additionally
stops/disables the timer/service and removes unchanged owned integrations. Edited
files remain and appear in the report. Source checkout, cached artwork and recovery
journals remain. To reinstall: `python3 install.py`. Use `app-faces resume` if a
previous rollback explicitly paused automatic matching.

## Code entry points

| Area | Implementation |
| --- | --- |
| Identity/providers | app_faces/core.py, identity.py, bundles.py, catalog.py |
| Automatic work | app_faces/automatic.py |
| Changes and recovery | app_faces/state.py, installation.py, launchers.py |
| Native UI/contributions | app_faces/ui.py, onboarding.py, community.py |
| KDE | app_faces/kde.py, adapters/kde/ |
| Worker/moderation | backend/src/, backend/migrations/ |

Python has strict mypy across the application package; two GTK dynamic GI superclass boundaries
have narrow type ignores. The backend, browser dashboard and backend tests use strict
TypeScript, including the separate browser E2E target. Lockfiles pin development dependencies; native GTK/KF libraries come
from the distribution.

## Verification evidence

- Python unit/integration suite: **127 passed; 2 GTK checks passed separately with a graphical display**, recorded in `state/first-pass-check.json`.
- Worker/D1: **16 passed** and strict TS clean: `state/checks-backend.txt`.
- Real GVFS install/uninstall/reinstall: five lifecycle checks (`state/lifecycle-integration.json`, local).
- Actual client-to-Worker roundtrip: seven integration checks (`state/community-integration.json`, local).
- Browser UI: **9 Firefox scenarios passed**, including responsive/accessibility checks: record (`state/moderation-ui-checks.json`, local), [flow scope](MODERATION-FLOWS.md).
- Published UI: **6 read-only checks passed** in Firefox: record (`state/production-ui-smoke.json`, local).
- Native integrated E2E: **nine checks passed** through real Files/GTK/Firefox
  and production, with a second native consumer file and both Undo paths.
  Result (`state/native-e2e/result.json`, local); isolated Xvfb/private D-Bus, synthetic
  fixtures only. This does not verify personal Wayland dock grouping.
- KDE: live isolated Dolphin preview → menu → GTK chooser passed;
  [evidence, compatibility and coordinate-fallback limit](../adapters/kde/README.md).
- Receipt correction/withdrawal: six production client checks (`state/production-receipt-lifecycle.json`, local).
- Real app coverage: [24 installed apps plus OCCT](APPLICATION-COVERAGE.md).

## Backend review

From `backend/`: `npm run init:local`, `npm run migrate:local`, `npm run dev`.
Open `http://localhost:8787/admin`. The local reviewer token is stored in private
`backend/.dev.vars`; it is not committed or printed in test output. There is no
contributor login. The reviewer token is used only to unlock moderation.

To exercise the client against the running local backend without changing personal
config, run `uv run python tests/integration/community_integration.py`. It creates its own
SVG fixture and disposable XDG directories. Existing application icons are not
uploaded by any automated test. Local Apply never depends on backend availability.

Godot dock grouping and launcher removal now pass in the personal session
for native Wayland and XWayland, including two windows under one correct icon;
see [dock E2E](DOCK-E2E.md). Visual overview result/click/removal also passed; broader portable-app coverage
remains open. Cloudflare production is deployed on the Free plan, using D1 only; see [DEPLOYMENT.md](DEPLOYMENT.md). The redesigned moderation UI was exercised in Firefox locally and on the published
endpoint, with locally inspected desktop/mobile captures. Remaining browser flow
gaps and native UI acceptance are explicit in [the crosscheck](ROADMAP-CROSSCHECK.md).

final verification summary (`state/first-pass-check.json`, local). Source archive and wheel were built; archive contents were checked to exclude local secrets, runtime data and node_modules.

## Real OCCT executable

real-file test result (`state/occt-integration.json`, local) and
[tests/integration/application_integration.py](../tests/integration/application_integration.py). Tested the actual
182,838,777-byte ELF in Downloads, without launching it. The real scanner found
it, but the current unmodified catalog returned **unknown**. This is a coverage
gap, not successful out-of-the-box OCCT recognition.

An explicitly seeded, temporary SHA256 mapping to the official site's favicon
then exercised the real automatic resolver, normalized icon storage and GVFS on
that same file. Automatic application, Undo and prevention of reapplication all
passed. The binary hash/mode and original icon were restored/unchanged. The mapping
was deleted with the original isolated test state. Subsequently, Nathan authorized
a reversible user-local exact-build mapping using that evidence and the local
official favicon. It now resolves that same build through SHA256; nothing was
uploaded, and generic OCCT support is not claimed. [Current provenance and rollback](APPLICATION-COVERAGE.md).

Run explicitly in the graphical desktop session:
`PYTHONPATH=. python3 tests/integration/application_integration.py --path /path/to/app
--icon /path/to/icon.png --app-id org.example.App --name Example
--artwork-source https://example.org/art --output state/application-integration.json`.
This opt-in test mutates and restores that file's icon; it is not run by unit CI.

live deployment, HTTPS auth and boundary PNG checks: production smoke (`state/production-smoke.json`, local); actual client/approval/revocation: production integration (`state/production-integration.json`, local).


## Real upstream artwork: Godot defect regression

native upstream result (`state/native-e2e/upstream-result.json`, local),
[defects, fixes and limits](PORTABLE-NEGATIVE-CASES.md). The actual official
Godot portable ELF initially missed the chooser's search despite upstream artwork
being available. Shared filename normalization fixes that search. The same real
case then caught stale Files rendering despite correct metadata; a reversible,
journaled user-xattr marker now triggers refresh.

The test starts without cached artwork, selects the pinned upstream Godot icon,
verifies normalized PNG bytes and the actual Files tile, then confirms Undo removes
the face without manual reload. A misleading Telegram filename is left untouched
by the background scan. These are concrete false-negative, visual-refresh and
false-positive regressions, not more synthetic coverage counts.

The refresh marker requires writable user-xattr support, preserves content/mode/
mtime but changes ctime. Unsupported filesystems get a refresh hint instead of a
false visual-success guarantee. No executable launch or community upload occurred.

## Configured sources and recovery follow-up

[source configuration](UPSTREAMS.md), Telegram accepted flow (`state/native-e2e/telegram-selfhst/upstream-result.json`, local),
configured-source accepted flow (`state/native-e2e/configured-selfhst-mirror/upstream-result.json`, local),
file lifecycle (`state/file-lifecycle-e2e.json`, local). These close the additional source,
real second-artwork and file move/replacement gaps. Sources now have separate adapters,
TOML configuration, deterministic priority and independent failure handling. Real
background scanning respects moved inode history, replacement identities and external
user choices. The stronger image oracle rejects generic and wrong-shape icons rather
than passing on a matching color alone. No backend changes/deployment were required.

Dolphin cancellation and Apply/Undo now pass with actual preview checks, using
the explicit Refresh action required by the tested KIO. The chooser tells users
to press F5; immediate automatic redraw is not claimed. Evidence (`state/dolphin-live-e2e.json`, local).


## Internationalization and cleanup — 26 September 2026

English code and documentation; ten shared interface catalogs; RTL Arabic and
Urdu; localized desktop and web flows. Provenance is centralized in
[SOURCES.md](../SOURCES.md). Source limits and retry intervals have named constants;
routine comments and audit labels have been removed.

Validation: 173 Python checks plus 12 explicit GTK checks in an isolated display,
16 Worker/D1 integration tests, and 20 Firefox scenarios (the original nine,
ten language flows, and blocked-storage/fallback recovery). Strict Python and
TypeScript checks and formatting pass. Translation wording still needs independent
native-speaker review. See [language support](I18N.md).


## Assertion quality audit — 26 September 2026

Strengthened bundle ambiguity/non-execution, AppStream traversal, fingerprint
cache reuse, native Apply arguments, persisted upload privacy and moderation access
checks. Backend cases now create independent Worker/D1 state. Removed KDE
source-string assertions; compiled-plugin checks validate pixels and execution
markers. See [test quality](TEST-QUALITY.md) for the assertions and boundaries.

Validation: 177 Python tests, 12 isolated GTK component cases, 16 backend cases
including shuffled execution, the compiled KDE CTest, and six targeted mutation
checks. Python/TypeScript checks and formatting pass. Production behavior is
unchanged; no deployment was required.


## Repository layout verification — 26 September 2026

The generic GTK fixture passed the isolated GNOME dock runner: one associated
launcher, one mapped entry and matching screenshot pixels. No OCCT process was
launched and no personal launcher/icon was changed. The native runner at its new
path passed all 12 GTK cases. Python checks passed 180 cases; backend integration
passed 16 and Firefox passed 20. Six targeted mutation checks still detect their
deliberate defects. Source/wheel archives contain the intended files and exclude
local reports, generated backend output and the removed vendor artwork.

Historical application observations above describe earlier runs. Current fixture
locations and runner boundaries are in [repository layout](REPOSITORY.md).
