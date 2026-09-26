# App Faces — first-pass roadmap

Updated 2026-09-26. Code and verification links below. The full original
acceptance specification is preserved in [docs/INITIAL-ROADMAP.md](docs/INITIAL-ROADMAP.md).
Checked boxes mean implemented and exercised at the stated boundary; live desktop
and production acceptance are listed separately, not silently assumed.

This is the source outline for future product, user, contributor and maintainer
documentation, not only a list of future tasks. Preserve the delivered behavior,
decisions, regressions and evidence below when deriving those documents. The
verification records describe completed runs; updating this document does not
mean those suites were rerun. Unchecked items are not shipped promises.

## Current status

The first-pass implementation is complete and deployed for review. The current
web interface has a minimal icon-led login, dark theme, top navigation and centered
review dialogs. Browser preferences select the language; there is no language
selector or saved web override. The README describes installation, automatic
scanning, manual selection and recovery.

Remaining validation:

- [ ] Broader application/build and distribution coverage, including Plasma dock integration.
- [ ] Confidence calibration against a representative labeled sample. The 0.90 threshold is a heuristic score, not measured accuracy.
- [ ] Sustained load with concurrent moderators.
- [ ] Manual screen-reader and assistive-technology review.
- [ ] Independent native-speaker review of all translations.

Recent web changes passed 23 Firefox scenarios, strict TypeScript, formatting and
six read-only production checks. Earlier native/backend results retain their own
execution dates and boundaries below. The repository remains one root commit;
release approval is pending until Nathan says “ok released”.

## Delivered for review

- [x] Local identity resolver: custom-icon and .desktop precedence, XDG overrides,
  Hidden/NoDisplay, GLib Exec parsing, wrapper ambiguity and theme icon resolution.
- [x] AppStream XML/gzip metadata, stat-cached SHA256 recognition, versioned local
  catalog import/rollback, conservative filename evidence. No executable execution.
- [x] Embedded Type2 AppImage icon/identity extraction using bounded unsquashfs,
  including real SquashFS fixtures and rejection of traversal/unsafe SVG.
- [x] Automatic user service/timer, heuristic threshold0.90, bounded scans/downloads,
  offline cache, positive/negative results and changed-file/catalog/theme invalidation.
- [x] Native GTK4 chooser: search, local image, Apply, Undo, application name,
  Add to applications, optional Upload when Apply. No manual catalog-load button.
- [x] GNOME Files Scripts integration using GVFS per-file custom icons. Chosen
  artwork is normalized/copied locally; user choices override automation.
- [x] Launcher reuse and explicit generation with safe quoting, known app IDs or
  WM class, ownership tracking and independent removal. Browsing never adds launchers.
- [x] selfh.st and Dashboard Icons adapters plus approved community catalog, source
  attribution, immutable local image copies and digest checks. Existing CDN research
  retained in [CATALOG-RESEARCH.md](docs/CATALOG-RESEARCH.md).
- [x] Optional install-time sharing preview, all rows unselected; anonymous uploads,
  allowlisted identity/image fields, retry queue and idempotency. Receipt status and
  retry, correction resubmission and withdrawal are available through the client;
  receipt-authenticated edits/withdrawals cover pending or correction states only.
- [x] Cloudflare Worker + D1 metadata/private artwork: upload throttling, image validation and
  normalization, content deduplication, private pending queue, public approved catalog.
- [x] Moderator dashboard and roles: approve, reject, merge, correction, revoke,
  revision rollback and reviewer audit. No contributor accounts or authorship identity.
- [x] Redesigned moderation web UI: password entry, searchable queue, centered review dialog,
  readable history/revisions, recoverable confirmations, responsive layouts and
  automated accessibility checks. Evidence: web UI checks (`state/moderation-ui-checks.json`, local).
- [x] KDE context menu and native Qt6/KF6 thumbnail plugin with shared resolver,
  compiled plugin roundtrip test, opt-in install and tracked removal.
- [x] Pause/resume, per-file Undo, global rollback, uninstall and reinstall. Stop
  background work before recovery; preserve subsequent user edits; retain recovery
  data and artwork needed by preserved references.
- [x] uv/Python3.14, strict mypy, Ruff, pytest; modern pinned Node/TypeScript/Cloudflare
  dependencies, strict Worker/dashboard/backend-test/browser-test types, actual workerd/D1 test suite.

## Verification performed

[REVIEW.md](docs/REVIEW.md), [tests](tests), [backend tests](backend/tests),
state/community-integration.json (`state/community-integration.json`, local),
state/lifecycle-integration.json (`state/lifecycle-integration.json`, local), and
[KDE build/test record](adapters/kde/README.md).

- [x] Native GTK chooser rendered and inspected locally.
- [x] Real GVFS apply and restore, including the actual OCCT ELF in Downloads.
  OCCT baseline remains unknown; an explicit user-local exact-build mapping now
  resolves it without publishing its hash or artwork. See docs/APPLICATION-COVERAGE.md.
- [x] Isolated HOME install → apply → launcher → uninstall → reinstall; actual GVFS.
- [x] Python client → local Worker contribution → private receipt → approval →
  manifest/download → revocation → mapping removal and asset404.
- [x] Native KDE plugin dynamically loaded and tested against shared Python helper.
- [x] Firefox UI flows against the local Worker + ephemeral D1, including
  decision failure/retry, correction cycles, cancellation, ten locales, delayed
  previews, keyboard focus recovery and desktop/mobile axe scans.
  [Flow coverage and limits](docs/MODERATION-FLOWS.md).
- [x] Published Firefox login → queue → history → revisions → logout checked read-only.
  Production browser evidence (`state/production-ui-smoke.json`, local).
- [x] Ownership preservation, concurrent review conflicts, upload throttling,
  revoked-artwork rollback filtering and malformed data covered by automated tests.

## Target-environment acceptance

- [x] Production Cloudflare provisioning/deployment on Workers Free, using D1
  for metadata and PNGs. Upload/approval/download/revocation tested remotely.
  R2 removed; see [DEPLOYMENT.md](docs/DEPLOYMENT.md).
- [x] Actual Files tile updates and Undo for an official Godot portable ELF,
  using uncached pinned upstream artwork, without manual reload.
  [Defects fixed and evidence](docs/PORTABLE-NEGATIVE-CASES.md).
- [x] Real personal-session Godot dock grouping in both Wayland and XWayland:
  two windows, one correct icon, launcher removal and generic-baseline restoration.
  [Saved flow and boundaries](docs/DOCK-E2E.md). Broader application coverage remains open.
- [x] Live Dolphin preview → context menu → chooser → cancel → Apply/Undo in
  isolated Xvfb. The tested KIO requires Refresh/F5 to redraw; the UI now says so.
  Real Plasma shell/dock and other distribution versions remain unverified.
  [Evidence and exact limits](adapters/kde/README.md).
- [x] Deterministic 24-installed-app + real OCCT benchmark, with identity and
  artwork measured separately. [Results](docs/APPLICATION-COVERAGE.md).
- [ ] Broader portable-build coverage and confidence calibration. Scores
  are explicit product heuristics; no claim of statistically measured90% accuracy.
- [x] Complete the second saved real upstream E2E: Telegram from selfh.st,
  including cancel, visible Apply and Undo without reload. Spatial image matching
  replaces the fragile exact-RGB assertion; detailed evidence is below.
- [x] Configurable GitHub upstreams/forks and separate metadata adapters.
  [Configuration, lifecycle and live configured-source E2E](docs/UPSTREAMS.md).

## Crosscheck and remaining implementation work

[2026-09-26 crosscheck](docs/ROADMAP-CROSSCHECK.md) compares the original
milestones with source, test cases and saved execution evidence. This was a code /
evidence audit, not a new execution of every desktop or production test. There is
no meaningful single completion percentage: implementation and live acceptance
have different boundaries.

Implementation items closed by the crosscheck and follow-up work:

- [x] Complete isolated real Files → native chooser/file picker → Apply/Undo →
  explicit opt-in upload → Firefox production approval → background sync and
  verified download → second native file search/Apply/Undo → browser revocation.
  Nine checks (`state/native-e2e/result.json`, local). Real Nautilus/GTK/Firefox on Xvfb;
  personal Wayland dock behavior is a separate acceptance boundary.
- [x] Refresh native chooser/onboarding wording, hierarchy, accessible labels and
  contribution status/retry/correction controls. The native integration above
  exercises the actual GTK chooser, beyond component rendering alone.
- [x] Seed user-identified exact OCCT build locally with reversible catalog backup;
  benchmark 24 installed applications plus OCCT without cherry-picking successes.
  Generic OCCT versions and portable builds remain outside that single-build claim.
- [x] Validate real Godot dock grouping, search registration/removal and launcher
  recovery in the personal Wayland session, with native Wayland and XWayland windows.
  [Evidence](docs/DOCK-E2E.md).
- [x] Real overview search result and click-to-launch for Godot on Wayland/XWayland,
  with result disappearance after launcher removal. [Dock/search flow](docs/DOCK-E2E.md).
- [x] Real GVFS move, journal migration, Undo at the new path, replacement-inode
  rejection, stale automatic-art cleanup and external-choice preservation.
  Saved file lifecycle (`state/file-lifecycle-e2e.json`, local). Other app builds remain an expansion area.
- [x] Extend Firefox flows for merge, stale review after contributor changes, lost
  response after commit, and reauthentication preserving a draft. Nine scenarios
  pass; prolonged load and actual assistive-technology review remain separate.
- [x] Receipt-authenticated contributor correction and withdrawal, idempotency and
  stale-version protection. Six real-client production lifecycle checks passed.
  Published artwork still requires moderation rather than contributor deletion.
- [x] Pin provider metadata and asset URLs to immutable upstream commits, retaining
  per-asset source URLs. Collection attribution does not establish every brand's
  redistribution permission; legacy unpinned records remain distinguishable.
- [x] Define retention as preserve/no automatic pruning and enforce a 256 MiB
  artwork admission ceiling; expose administrator storage report. No paid services
  or destructive retention job were introduced. Free platform limits still apply.
- [x] Validate actual Dolphin preview/menu/chooser with extracted runtime and publish
  current compatibility matrix. The local KF6 build is not a portable release artifact.

The early thumbnailer/Shell-extension investigation was superseded by the explicit
GVFS + Files script and launcher route below. It is an architecture decision, not
a missing extension secretly counted as implemented. The original snapshot remains
historical; this file is the current checklist.

## Integration decisions

GVFS plus a Files script is the shipped GNOME route. A Shell extension is not
required for file icons or ordinary desktop launchers. Shell window association
uses an app's actual app ID/WM class; a generic extension cannot invent one.
The chooser is a properties-adjacent action, not an unsupported embedded Nautilus
properties widget. KDE uses its native preview API and requires previews enabled.

The backend reuses public providers for known artwork and supplies the separate
anonymous contribution/moderation workflow. Pending assets never become public
through upload alone. Exact binary hashes remain local unless separately introduced
as an explicitly consented future contribution feature.

## Required deployment budget — free only

Nathan requires zero cost; production now uses Workers Free + D1 only.
The R2 version was replaced before deployment. Fixed Free CPU/request/storage/query
quotas apply; reaching them may make the service unavailable, never authorizes an
upgrade. Production boundary samples and provenance: [DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Delivered behavior to carry into the documentation

[DEVELOPMENT.md](DEVELOPMENT.md), [resolver](app_faces/core.py),
[recovery implementation](app_faces/state.py), and the evidence linked above.

### Recognition, automation and user control

The product should make known applications acquire useful icons in the background.
There is no user-facing catalog “Load” step. The installed user service/timer scans
configured locations, refreshes catalogs and uses local caches when offline. The
default locations include Downloads, Desktop, Applications, .local/bin and existing
launcher targets under the user's home. Current bounds include depth 2, 10,000
entries, 2,000 candidates, three remote artwork requests per scan and a 15-second
settling period for newly modified files. Provider metadata refreshes daily;
community metadata refreshes every five minutes.

Existing custom icons and authoritative local desktop associations take precedence.
The resolver also understands embedded Type2 AppImage artwork, optional known exact
SHA256 mappings and AppStream evidence. Ambiguous wrappers or multiple executable
associations do not become automatic matches. Executables are inspected, never run
to discover identity. Recognition and artwork availability are separate results:
a provider having a Telegram icon does not prove a file named Telegram is Telegram.

Automatic assignment uses a heuristic threshold of 0.90. Plain filename suggestions
score 0.60 and require an explicit choice. These are rules, not calibrated
probabilities or a measured 90% success rate. User choices override background
work; Undo opts that inode out of automatic reapplication. Positive and negative
cache entries are invalidated when the relevant file/catalog/desktop/theme changes.

### Files, application search and dock are separate surfaces

GNOME Files uses GVFS per-file custom-icon metadata and a Files script that opens
the GTK chooser. The chooser supports search, a native local-image picker, Apply,
Undo, application naming, optional launcher creation and optional contribution.
It is a context action, not an embedded Nautilus properties panel. A Shell extension
was investigated early but is not the shipped integration.

Application search and the dock use desktop launchers and real application/window
identity. Existing launchers are reused; explicit creation safely quotes arguments,
records ownership and can use a known app ID/WM class. Browsing or choosing a file
icon does not silently create a launcher. Changing a Files tile does not prove a
running window groups correctly in the dock.

**Godot dock acceptance passed in the personal session.** The native Wayland and
XWayland flows each verified a generic baseline, search registration, launch from
the generated desktop entry, two windows grouped under one mapped dock actor with
the expected managed icon, launcher removal, and a reopened generic baseline.
Screenshots were inspected locally. [Runner, identities and evidence](docs/DOCK-E2E.md).
Visual overview search and click-to-launch now also pass for both display modes.
Favorites, other applications and mismatched identity collisions remain separate cases. A launcher cannot invent an app's own
window identity; these tests used the identities actually announced by Godot.

KDE has an optional Qt6/KF6 thumbnail plugin and context menu. A compiled plugin
roundtrip and real isolated Dolphin preview → menu → chooser → cancel → Apply/Undo
are verified. Apply and Undo require a real Refresh action in Dolphin 25.12.3 /
KIO 6.24.0; the chooser explicitly instructs the user to press F5. KIO compares
stat fields unchanged by this journal-backed preview and does not regenerate it
from our marker alone. No false automatic-refresh claim or broad cache clearing
was added. Plasma dock, other distributions and portable binary packaging remain
separate. Evidence (`state/dolphin-live-e2e.json`, local).

### Contribution and moderation lifecycle

Reuse existing public icon collections before building a duplicate CDN. The
community service supplies missing or corrected artwork through an anonymous,
moderated workflow. Contributor identity/login is not required. Installation-time
sharing is an optional preview with every row initially unselected; “Upload when
Apply” is also opt-in. Local icon application does not depend on upload succeeding.

Submissions contain allowlisted app identity/name, normalized PNG and provenance/
license/variant fields, not raw .desktop files, launch commands, local paths or
binary fingerprints. Upload throttling, bounded image processing, deduplication,
idempotency and a retry queue are implemented. A private receipt supports status,
correction and withdrawal while pending or awaiting correction. Publication is a
moderator action; published assets require moderated revocation rather than direct
anonymous deletion. Unknown license information is not silently treated as approval.

The moderator web interface includes authenticated access and roles, a searchable
queue, centered review dialog, correction/reject/approve/merge actions, history, revocation
and revision rollback. Contributor accounts remain absent. UI checks include
desktop/mobile layouts, accessibility scans, cancellation, errors/retry, stale
decisions and reauthentication with a preserved draft. Manual assistive-technology
review and sustained load testing remain outside the completed evidence.

### Recovery and operating budget

Pause/resume, per-file Undo, global rollback, uninstall and reinstall are part of
the product. Rollback stops background mutation first, restores owned changes and
removes unedited generated launchers. Later user edits must survive. Corrupt journals
fail closed; incomplete recovery is reported rather than discarded. Cached artwork
and recovery records can remain because preserved references may need them.
Uninstall's explicit keep-icons option is documented separately from normal rollback.

Production uses Workers Free and D1 for both metadata and private normalized PNGs.
R2 was removed before deployment. Artwork admission has a 256 MiB ceiling and an
administrator storage report; retention preserves records without automatic pruning.
Free request/CPU/storage/query quotas still apply. No automatic paid upgrade is
authorized. Deployment, migrations and authentication operations belong in
[DEPLOYMENT.md](docs/DEPLOYMENT.md); do not copy credentials into documentation.

## Regression history and real E2E evidence

Tests model user journeys and state transitions, including cancellation, abstention,
failure and recovery. Counts are supporting records, not the product acceptance
criterion. A metadata assertion alone cannot establish that a person saw the icon
change. Keep each flow's initial conditions, transitions, observable result and
untested boundary alongside its evidence.

| Flow | Recorded outcome | Evidence / boundary |
| --- | --- | --- |
| Isolated Files → chooser → native image picker → Apply → Undo | Passed | First part of native flow (`state/native-e2e/result.json`, local); real Nautilus/GTK |
| Explicit upload → production Firefox approval → background sync/download → second file Apply/Undo → revocation | Passed, nine checks across the combined journey | Same native record; synthetic artwork, private Xvfb/D-Bus, production Worker |
| Official Godot 4.7.2 → Dashboard Icons, initially empty artwork cache → visible Files Apply/Undo | Passed without folder reload | Godot result (`state/native-e2e/upstream-result.json`, local) |
| Unrelated ELF renamed Telegram → automatic scan | Abstained as required | Godot result and portable baseline (`state/portable-coverage.json`, local); filename alone is insufficient |
| Official Telegram 7.2.9 → selfh.st → cancel/reopen → visible Apply/Undo | Passed without reload | Telegram result (`state/native-e2e/telegram-selfhst/upstream-result.json`, local); spatial matcher rejects generic/wrong icons |
| Configured selfhst-mirror → sync → Telegram native Apply/Undo | Passed with built-in providers disabled | Configured-source result (`state/native-e2e/configured-selfhst-mirror/upstream-result.json`, local); new source namespace, existing public repository |
| File move/replacement/external edit → scan/recovery | Passed with real GVFS and scanner | File lifecycle (`state/file-lifecycle-e2e.json`, local); no fixture execution |
| Dolphin cancel → Apply → Refresh → Undo → Refresh | Passed, explicit manual refresh required | Dolphin result (`state/dolphin-live-e2e.json`, local); correct preview transitions and unchanged binary/mode/mtime |
| OCCT in Downloads | Real GVFS lifecycle and local exact-build recognition checked; clean upstream lookup misses | [coverage](docs/APPLICATION-COVERAGE.md); not generic OCCT recognition |
| Real Godot dock/window grouping | Passed native Wayland and XWayland in the personal session | [Dock E2E](docs/DOCK-E2E.md): two windows, one correct icon; search registration and launcher removal/reopen |

### Godot exposed two product defects, both corrected

1. The versioned filename `Godot_v4.7.2-stable_linux.x86_64` initialized the chooser
   with a query that hid an existing upstream result. Resolver and chooser now
   share `application_search_name`; the initial search offers Godot without manual
   query repair. This improves suggestions without granting automatic identity.
2. Correct GVFS metadata and downloaded bytes did not refresh Nautilus's existing
   tile. The client now journals a `user.app-faces.icon` xattr to trigger the file
   monitor and restores/removes its owned marker on Undo. Inode/device checks,
   prior marker bytes and subsequent external edits are respected. Contents, mode
   and mtime are preserved; ctime changes. If xattrs cannot be used, metadata can
   still be saved and the UI gives a folder-refresh notice.

The accepted Godot run verified downloaded/applied normalized bytes and the actual
file tile, with no manual reload: artwork-colored pixels were 0 before, 1,143 after
Apply and 0 after Undo. Local screenshots are retained under `state/native-e2e/` as
`upstream-files-before.png`, `upstream-files-applied.png` and
`upstream-files-restored.png`. [Detailed analysis](docs/PORTABLE-NEGATIVE-CASES.md).

### Telegram: second case accepted, test defects preserved

[tests/integration/e2e-telegram.sh](tests/integration/e2e-telegram.sh) selects the real Telegram fixture,
the pinned selfh.st provider and a separate evidence directory. The accepted run
passes preview cancellation with no mutation, reopen, download/Apply, actual visible
Files artwork and Undo to the generic icon, without reloading the folder.
Result (`state/native-e2e/telegram-selfhst/upstream-result.json`, local).

The initial exact-dominant-RGB oracle failed on gradient/downsampled artwork despite
a correct visible icon. It was replaced with spatial artwork-template matching,
including light details and aspect ratio. Real saved before/applied/restored images,
wrong-app images and a mirrored airplane with the same palette distinguish a correct
render from a merely similar color. Nine saved-image checks pass; a synthetic
resize/geometry regression exercises the oracle independently. The accepted Telegram
match has mean channel error 0.248/255 and matching fraction 1.0. Before/Undo reject.

A second instrumentation issue was GTK4 AT-SPI tile coordinates excluding invisible
window shadow margins. The matcher searches a bounded local region around the tile;
it does not search the entire screen or the chooser preview. The original failed
run is retained in `state/native-e2e/telegram-selfhst-exact-rgb-failure`.
[Oracle design and evidence](docs/PORTABLE-NEGATIVE-CASES.md).

The same complete flow also passes with a source declared only in TOML under
`selfhst-mirror`, built-in providers disabled and a fresh artwork cache.
[Configured-source acceptance](docs/UPSTREAMS.md). This uses the existing public
repository under a new local ID, not a newly created GitHub fork.

Fixtures come from official Godot/Telegram downloads via bounded acquisition;
URLs and locally computed hashes are in the ignored build manifest. These Files
flows do not execute binaries or upload icons. The separate dock flow does execute
Godot, with test-only configuration and dummy audio. Screenshots remain local.

### “Allow Remote Interaction” was a test-isolation defect

The observed portal request was traced to local Xwayland on the personal display.
The earlier wrapper started private D-Bus before Xvfb, allowing the activated
accessibility service to inherit the personal DISPLAY. Synthetic pointer input
then reached Xwayland's input-emulation portal. This was not evidence of an incoming
RDP attack. Diagnosis (`state/native-e2e/remote-dialog-diagnosis.json`, local).

The wrapper now starts Xvfb before private D-Bus, clears inherited Wayland/DBus/
AT-SPI addresses and uses xdotool only on the private display. Isolation checks
validate the Xvfb server and the activated accessibility process before input.
The subsequent monitored run contained no RemoteDesktop calls. Keep this launch
order and preflight invariant in test-maintenance documentation; do not restore
the old personal-session synthetic-input path.

## Configurable upstreams and forks: delivered extension contract

[upstreams.py](app_faces/upstreams.py), [source tests](tests/test_upstreams.py)
and [configuration/maintainer guide](docs/UPSTREAMS.md). The earlier hardcoded
provider repository table/parser branch has been replaced by validated source
configuration plus an adapter registry.

- [x] `upstreams.toml` declares stable ID, GitHub repository, format, branch/tag/SHA,
  enabled state and priority. Edits refresh on the next background scan with
  configuration-aware retry backoff and recognition-cache invalidation. Mutable refs
  resolve to immutable revisions; defaults preserve selfh.st and Dashboard. `app-faces sources` validates/lists effective sources.
- [x] Separate selfh.st/Dashboard adapters normalize records. Shared logic handles
  bounded retrieval, identifiers, pinning, source provenance, images, caching and rollback.
- [x] Source IDs namespace catalog/cache records; lower numeric priority sorts
  suggestions deterministically. It does not override a custom icon or raise confidence.
- [x] Disabling/removing a source hides suggestions while retaining installed artwork,
  cache/history and offline pinned assets. Healthy sources update despite another
  failing; all-source failure preserves the working snapshot.
- [x] Tests cover new adapter formats, same-schema sources, duplicate/conflicting
  slugs, invalid config/metadata, missing artwork, offline cache, outages and rollback.
  A new source ID configured against the real pinned selfh.st repository passed the
  complete native Telegram Cancel/Apply/Undo flow with built-ins disabled.
- [x] Document actual configuration, disable/remove semantics, failures and extensions
  in [UPSTREAMS.md](docs/UPSTREAMS.md).

Current transport scope is public GitHub repositories with `png/SLUG.png` assets.
New metadata formats require an adapter; other hosting or asset layouts also require
transport changes. Anonymous community moderation remains a separate path. No
contributor login, extra CDN deployment or per-brand licensing assumption was added.

## Documentation handoff and next acceptance order

Use this roadmap to derive user installation/use/recovery docs, contributor and
moderator flow docs, an architecture/provider extension guide, and a test operations
guide. Preserve the original proposal in [INITIAL-ROADMAP.md](docs/INITIAL-ROADMAP.md)
and the requirement crosscheck in [ROADMAP-CROSSCHECK.md](docs/ROADMAP-CROSSCHECK.md).
Detailed evidence belongs in linked records rather than copied secrets or screenshots
published without permission.

The initial crosscheck recorded 144 Python tests plus two GTK checks run separately,
16 Worker/D1 tests, nine Firefox UI scenarios, four strict TypeScript configurations,
strict mypy across 16 modules and a native KDE test. Later verification is recorded
in the dated sections below and in Current status above. These are execution
records, not a fresh run caused by this roadmap edit. See
first-pass check (`state/first-pass-check.json`, local) for deployment/version references.

The first-pass implementation gaps identified in this crosscheck are now closed:
Telegram, configured sources, visual overview activation and file lifecycle recovery
all have saved acceptance evidence. Broader app/distribution samples, statistically
calibrated confidence, sustained load and manual accessibility review remain explicit
future validation work, not claims established by this small regression set.

## Persistent OCCT customization — 26 September 2026

At Nathan's request, custom SVG and PNG artwork were created and applied locally to
`~/Downloads/OCCT` through App Faces. A persistent owned `OCCT.desktop` launcher
uses observed WM_CLASS `OCCT` (instance `OCCTGUI`). After closing and launching
through that desktop entry, Shell associated the real window with `OCCT.desktop`
and its dock GIcon referenced the new managed PNG. Binary bytes were unchanged.
Local evidence (`state/occt-custom-flow/result.json`, local). No contribution was uploaded.

The user was actively watching fullscreen VLC, so the dock actor was not mapped:
this confirms registration/association, not a final visible dock screenshot. The
customization remains installed for subsequent launches. Personal-desktop tests
now distinguish this busy/occluded condition from a product failure and do not
claim a visual pass or repeatedly steal focus.

The follow-up visual proof passed on an isolated GNOME Shell with the actual Ubuntu
Dock extension and real OCCT executable. The runner copies the persistent desktop
entry byte-for-byte, checks its actual window association and one mapped dock entry,
and compares screenshot pixels against the original custom PNG. The image matched
exactly in the accepted screenshot (mean channel error 0, matching fraction 1).
The initial private FUSE cleanup failure was corrected; the complete rerun exited
0 and left no temporary shell directories. This does not replace the distinct
personal-session association evidence above. Visual proof (`state/occt-isolated-dock/result.json`, local),
[saved runner](tests/integration/isolated-app-dock.sh),
[article: “How robust?” “Yes.”](docs/CHAOS-MONKEY-DESKTOP.md).

## Additional downloaded applications, without execution — 26 September 2026

KeePassXC 2.7.12 and QOwnNotes 26.9.11 official x86_64 AppImages were downloaded
to Nathan's Downloads directory and checked against their published SHA-256
digests. Their embedded icons were applied through App Faces; owned user launchers
were created with embedded desktop IDs and StartupWMClass values, then appended
to GNOME favorites without removing or reordering existing pins. Neither binary
was executed, including for extraction. Evidence (`state/downloaded-apps-pins.json`, local).

Both real packages exposed a missing case: their root desktop entries are relative
symlinks into `usr/share/applications`. The bounded archive reader now resolves
these with the existing archive-only resolver, retaining the root desktop ID.
Regression tests cover valid nested targets, external/absolute targets, cycles,
and multiple root desktop identities; all 12 bundle tests, Ruff and strict mypy
passed. Extraction uses `unsquashfs -cat`, never an AppImage extraction command.

Verification covers official digests, real bundle extraction, desktop-file-validate,
Gio launcher loading, exact launch command and persistent favorites roundtrip.
Running-window grouping and screenshot pixel verification were deliberately not
performed for these two applications: the user requested that they not be opened.


## Internationalization and source cleanup — 26 September 2026

The GTK chooser, contribution screens, onboarding and moderation dashboard use
shared English-keyed JSON catalogs for en, zh, hi, es, fr, ar, bn, pt, ru and ur.
Locale selection, fallback, named parameters and RTL layout are documented in
[I18N.md](docs/I18N.md). The later centered-login update removed saved web preferences;
browser language negotiation is the current behavior. Application identifiers, API
states and submitted content are unchanged by the display language.

Source strings, tests and documentation now use English. Routine source comments
were removed; behavioral limits, retry intervals, scan quotas and archive bounds
have named constants. Provenance is recorded in [SOURCES.md](SOURCES.md), linking
specifications to implementation and reproducible checks. Raw execution evidence
remains local under ignored `state/`.

The original nine moderation scenarios, ten language flows and a blocked-storage
fallback flow passed in Firefox against local Worker/D1. Translation wording has not been independently
reviewed by native speakers in every language. The repository remains a single
root commit until the owner declares “ok released”.


## Assertion quality audit — 26 September 2026

Strengthened bundle ambiguity/non-execution, AppStream traversal, fingerprint
cache reuse, native Apply arguments, persisted upload privacy and moderation access
checks. Backend cases now create independent Worker/D1 state. Removed KDE
source-string assertions; compiled-plugin checks validate pixels and execution
markers. See [test quality](docs/TEST-QUALITY.md) for the assertions and boundaries.

Validation: 177 Python tests, 12 isolated GTK component cases, 16 backend cases
including shuffled execution, the compiled KDE CTest, and six targeted mutation
checks. Python/TypeScript checks and formatting pass. Production behavior is
unchanged; no deployment was required.


## Repository layout and generic fixtures — 26 September 2026

OCCT artwork was removed from product assets. Generic processor artwork and a
minimal GTK application now live under `tests/fixtures/`. Dock tests take the
launcher, window class, expected image and output directory as inputs. Local
catalog seeding and file lifecycle checks also accept application identity and
artwork explicitly; coverage scripts have no personal Downloads path.

Desktop integration runners live under `tests/integration/`; KDE adapter tests
live under `adapters/kde/tests/`. Setup/check and catalog maintenance commands
remain under `scripts/`. Deployment, review and catalog research documents moved
to `docs/`. The generated web bundle moved from `backend/src/` to ignored
`backend/build/`. Historical OCCT observations remain documentation, not built-in
application recognition. See [repository layout](docs/REPOSITORY.md).


## Centered login — 26 September 2026

Replaced the split login with a centered card containing the brand, password field,
visibility control and sign-in button. Removed the decorative side panel and
language selector. Web language now follows browser preferences automatically,
falling back to English and ignoring the previous saved override. Desktop
language configuration is unchanged.

Browser coverage adds card centering at desktop and 320px widths, keyboard-only
submission and removal of the selector. Existing invalid-password, recovery,
accessibility and ten-language moderation flows remain covered.


## Moderation workspace — 26 September 2026

Replaced the sidebar and redundant access banner with a compact header and three
navigation destinations. Queue, history and catalog versions share one centered
content column. Contribution review now opens in a centered dialog with submitted
and published artwork side by side. Review actions and decision confirmation stay
visible while long content scrolls. Layout uses logical alignment for RTL.

Opening a review before its icon download completes now updates the preview in
place. A delayed-download browser scenario checks the decoded image without
closing or reopening the review. Responsive checks cover centered dialogs,
visible action buttons, keyboard focus restoration, navigation, and accessibility
at 1440px and 320px. Existing publication, recovery and ten-language flows remain
covered. Production verification uses read-only navigation; test contributions
remain in the isolated local database.


## Madame Sata visual theme — 26 September 2026

The moderation interface uses dark plum surfaces, burgundy actions, violet focus
and link colors, gold accents and serif page headings. Login, queue, history,
versions, review and confirmation share the same theme. Native form controls use
a dark color scheme. Artwork previews retain a light checkerboard to expose
transparent pixels without applying a filter to submitted images.

The existing responsive and keyboard flows remain covered. Automated accessibility
checks also inspect invalid-password feedback and decision forms. No new external
fonts, images, dependencies, preference controls or backend resources are needed.


## Minimal login — 26 September 2026

Login shows only the App Faces mark, password label/input and sign-in action.
Removed the visible product name, heading and description. Password visibility
uses an eye icon with localized accessible labels and a pressed state. Authentication
errors still appear when needed. The login region and brand retain accessible
names; keyboard navigation and browser-password-manager attributes are preserved.
