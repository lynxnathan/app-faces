# Historical planning snapshot

Superseded by ../ROADMAP.md; statements below describe the earlier implementation stage.

# Roadmap

Created 2026-09-25; expanded the same day with Nathan's contribution/moderation
flow and existing-provider research. The first native client is implemented; the milestones below retain their
individual completion state, including unimplemented automatic integration.
Checkboxes indicate delivered work within the stated scope.

## Delivered first slice — 2026-09-25

implementation record (`state/implementation-20260925.md`, local).

- [x] Native GTK4 icon chooser with local-image selection, existing-icon preview,
      community search, explicit Apply, and Undo.
- [x] Read-only resolver with user icon / desktop entry precedence, conservative
      wrapper handling, optional SHA-256 lookup and filename suggestions.
- [x] selfh.st and Dashboard Icons catalog/download adapters; 5,730 artwork entries
      fetched (including variants and duplicates), with offline search and cache.
- [x] User-local CLI and Files Scripts installation plus reversible removal.
- [x] uv lockfile, Ruff, strict mypy for core/state/CLI and 30 passing tests.
- [x] Real GVFS apply/undo in isolation and a rendered/inspected GTK window.
- [ ] Observe a full menu click and file-icon update in the user's Files session.

Follow-up: automatic application is now implemented through a user service/timer.
Rules scoring at least 0.90 apply without interaction; existing custom icons win.
The scores are heuristic rather than calibrated probabilities. There is no Load
button; catalog refresh is background work. Scope/limits and live verification
are recorded in the implementation record. AppStream/bundle extraction, Shell
integration and the contribution backend remain unfinished.

## Research completed and implementation direction

- [x] Review existing artwork services/CDNs and contribution systems; save the
      sourced comparison in [CATALOG-RESEARCH.md](CATALOG-RESEARCH.md).
- [x] Preserve Nathan's install-time contribution invitation, properties opt-in,
      Cloudflare backend direction, and approval-before-publication requirement.
- [ ] Benchmark candidate coverage and provider terms before selecting an adapter.

Nathan accepted reusing the researched catalogs. Direction: reuse
AppStream metadata, Dashboard Icons, and selfh.st where
appropriate. Keep our recognition mappings independent of artwork hosting. Build
our own upload/moderation service if existing services cannot cover the required
workflow; do not duplicate a full icon CDN merely to start the resolver.

## 0. Prove the desktop integration

- [x] Record installed GNOME Shell/Files/GTK versions and Wayland display.
- [ ] Evaluate extension APIs for automatic integration.
- [ ] Inspect a few user-selected examples: plain ELF, AppImage, and an app with
      an existing launcher. Record the actual file, launcher, and window IDs.
- [ ] Prototype both a thumbnailer and a Nautilus extension/custom-icon route.
      Determine which handles executable MIME types and renders artwork cleanly
      at the intended icon sizes without thumbnail frames or global CSS hacks.
- [ ] Check refresh, file moves, executable replacement, symlinks, and explicit
      custom icons. Record which behavior is supplied by Files versus our code.
- [ ] Demonstrate the separate Shell path with a temporary desktop entry and
      matching window identity. Do not assume Files changes affect the dock.

**Acceptance:** screenshots inspected locally and a written comparison identifying
one viable Files route and one viable launcher/dock route. Document version
limits and cleanup steps. Consult linux-setup instructions before altering the
live desktop; Nathan controls logout/reboot. No screenshot uploads.

## 1. Build a local resolver with desktop entries first

- [x] Implement a read-only CLI accepting a file path and returning structured
      identity, icon, match method, evidence, and ambiguity information.
- [ ] Read desktop entries through a standards-aware parser/GIO; respect XDG
      locations, user overrides, `Hidden`, and `NoDisplay` semantics.
- [ ] Handle `Exec` field codes, quoting, PATH lookup, wrappers, interpreter
      scripts, and symlinks deliberately. Never execute an `Exec` string during
      matching, and never treat it as an arbitrary shell command.
- [ ] Resolve themed icon names and absolute paths; preserve theme selection.
- [ ] Keep user overrides separate from generated matches and catalog data.
      Represent accept, reject, reset, and disabled automatic matching.
- [ ] Add bundle identity/icon extraction where supported, without executing or
      mounting the application as a prerequisite.

**Acceptance:** fixtures cover direct launchers, user overrides of system entries,
wrapper ambiguity, missing icon assets, symlinks, and an unknown executable.
No ambiguous association silently becomes a definitive match.

## 2. Define and seed the catalog

Proposed data model:

| Record | Essential fields |
| --- | --- |
| Application | Stable catalog ID, name, aliases, upstream identity |
| Artwork | Application ID, asset digest/path, source URL, license/attribution |
| Fingerprint | SHA-256, size, application ID, optional version/architecture, provenance |
| Filename rule | Anchored pattern, application ID, supporting constraints, provenance |
| User override | Local target identity, selected artwork/application or rejection |
| Provider mapping | Catalog application ID, provider, provider ID/slug, source revision |
| Submission | Proposed app identity/artwork, asset source, consent scope, status, timestamps; no contributor identity |
| Review | Submission ID, reviewer, decision/reason, previous decision, publication revision |

- [ ] Version the catalog format and define validation/import rules.
- [ ] Seed a small, provenance-backed collection of applications Nathan uses.
- [ ] Compute exact hashes asynchronously, caching results. Every different
      build can have a different hash; do not confuse a hash catalog with a
      version-independent application identifier.
- [ ] Treat ELF build IDs and other metadata as optional evidence, not universally
      available application names or globally trustworthy identity.
- [ ] Make filename rules conservative, bounded, and subordinate to stronger
      evidence. A renamed unrelated binary must not override an explicit choice.
- [ ] Track artwork redistribution permissions; link to upstream artwork when
      redistribution rights have not been established.

**Acceptance:** exact known builds resolve offline; changed and unknown builds
fall back predictably. Conflicting names produce an unresolved/suggested result.
One application can share artwork across multiple fingerprint records.

## 3. Ship the Files MVP

- [x] Connect the Files action to the resolver and local catalog.
- [x] Add a user service/timer for background recognition/application in watched
      directories; preserve custom icons and remember Undo as an opt-out.
- [x] Remove manual catalog loading from the UI; refresh automatically.
- [ ] Perform expensive work outside the file manager's UI thread with bounded
      queues, timeouts, size limits, and cancellation for abandoned requests.
- [ ] Cache successful and negative lookups; invalidate on file changes, catalog
      updates, theme changes, and user corrections as appropriate.
- [ ] Add a small user flow for choosing/correcting artwork and resetting it.
- [ ] Provide user-local installation and clean removal of project-owned state.

**Acceptance:** known executable files display their artwork in Files; unknown
files keep a sensible fallback; existing custom icons remain authoritative.
Opening a directory of large executables stays responsive. Moving/replacing a
file never leaves a stale confident association indefinitely. Uninstall restores
normal behavior without deleting unrelated settings or thumbnail caches.

## 4. Integrate app search and the dock

- [ ] Reuse existing desktop entries whenever they match; avoid duplicate launchers.
- [ ] Design an explicit “Add to applications” action for recognized applications
      without an entry. Merely browsing a folder must not populate the app grid.
- [ ] Generate user-local entries with correctly escaped executable paths and
      stable icon references, recording which entries the project owns.
- [ ] Verify Wayland app IDs and X11/XWayland window-class matching with real apps.
      Separate icon resolution failures from window association failures.
- [ ] Investigate a Shell extension only for remaining gaps; document supported
      Shell versions and a graceful fallback when unsupported.

**Acceptance:** the same chosen artwork appears in app search and the dock, with
correct running-window grouping for the documented test apps. Existing user
entries are not overwritten. Generated entries can be removed independently.

## 5. Reuse providers and publish catalog updates

- [ ] Benchmark candidate providers as described in CATALOG-RESEARCH.md; measure
      identity accuracy separately from artwork availability.
- [ ] Implement interchangeable provider adapters and map stable app IDs to
      provider IDs. Keep explicit local choices and desktop entries authoritative.
- [ ] Prefer locally available AppStream metadata; cache remote catalog metadata
      for local matching. Fetch artwork by known asset ID, not raw local filename.
- [ ] Select a catalog update mechanism with validation, versioned publication,
      atomic replacement, rollback, and repeatable source revisions.
- [ ] Record attribution and variant information with every asset. Avoid confusing
      an upstream application icon with a user theme or unofficial alternative.
- [ ] Preserve usable offline behavior and existing cached assets during outages.

**Acceptance:** a provider can be changed without rewriting recognition or desktop
adapters. New mappings can arrive through a catalog update. No filename, launch
arguments, or executable hash is sent during normal recognition. Asset fetches
are documented separately from optional contributions.

## 6. Optional contributions from installation and file properties

Nathan's requested product flow, 2026-09-25. The details below are the
proposed implementation of that flow.

- [ ] During install/onboarding, invite the user to help the shared catalog.
      Scan desktop entries locally and show a selectable preview of application
      names/identities and icons. Skipping leaves the application fully usable.
- [ ] Accept anonymous uploads without a contributor account, login, email, or
      contributor profile. Apply request throttling/rate limiting. Transport data
      used to enforce limits is transient operational data, not catalog authorship.
- [ ] Upload only selected icon assets and allowlisted application identity metadata. Do not
      send raw `.desktop` files, `Exec`/`TryExec`, local paths, arguments, environment
      values, or executable contents. Binary fingerprint contributions, if added,
      require their own explicit preview and are not implied by sharing an icon.
- [ ] In the icon properties flow, offer an unchecked “Upload when Apply” option,
      explaining that it submits the selected icon for community review.
- [ ] Apply locally immediately; submission success, failure, and review status
      must never block the local icon change. Retry without creating duplicates.
- [ ] Verify that the installed Nautilus API can host this control. If it cannot,
      provide a clearly labeled properties-adjacent dialog/context action rather
      than promising an unsupported native properties widget.
- [ ] Show the source and attribution fields and distinguish official artwork
      from custom/theme variants. App name alone is not a unique identity.
- [ ] Evaluate an existing provider's submission workflow first. Do not assume its
      website form is a public API that our client can automate.

**Acceptance:** no consent means no submission request. The preview accurately
matches the uploaded payload. Apply works offline; an upload failure is visible
and retryable. Pending artwork is usable by its submitter locally but is not
served to everyone as an approved application icon.

## 7. Cloudflare submission backend and moderation dashboard, if needed

Nathan selected Cloudflare as the direction for our own backend and
wants to approve contributions before they appear publicly, with community
reviewers possible later. The following service split is a proposal; exact
Cloudflare products, limits, pricing, and deployment details are not yet selected.

- [ ] Build an upload API, private pending asset storage, submission metadata,
      authenticated review dashboard, and separate approved catalog/CDN delivery.
- [ ] Use icon-content hashes for deduplication, separate from executable hashes
      used by recognition. Deduplicated images still need review of each proposed
      application association.
- [ ] Validate image formats, dimensions and size; normalize previews, strip
      unnecessary metadata, and prevent SVG active content/external references.
      Throttle anonymous submissions; do not introduce contributor authentication
      or reputation as a prerequisite. Bound technical processing costs.
- [ ] Give Nathan the initial reviewer/admin account; show artwork beside the
      proposed app identity, provenance, existing variants, and duplicate matches.
- [ ] Support approve, reject, merge, request correction, and withdraw/revoke.
      Publish neither pending assets nor pending mappings through public endpoints.
- [ ] Record reviewer decisions and published revisions. An icon replaced by
      vandalism must be reversible, including removal from subsequent client
      catalogs and invalidation of a revoked asset.
- [ ] Later add explicitly assigned community reviewers with limited roles.
      Anonymous upload endpoints cannot publish or grant review privileges.
- [ ] Publish immutable approved assets with versioned manifests; preserve
      source/attribution and handle correction/removal requests.

**Acceptance:** a submission travels from opt-in preview to private pending queue,
Nathan's review, and an approved versioned catalog update. Unreviewed or rejected
artwork cannot become the public default. Revocation and rollback are demonstrated.
Local use and existing provider adapters continue working without this service.

## 8. KDE integration and distribution

- [ ] Implement a Dolphin adapter against the same resolver contract and fixtures.
- [ ] Reuse contribution and review APIs; preserve the same precedence and consent.
- [ ] Package tested integrations and publish a compatibility matrix.
- [ ] Provide removal of project-owned entries/state without deleting user choices
      or unrelated desktop settings.

**Acceptance:** GNOME/KDE adapters agree on application identity and precedence;
users can install and remove each integration independently.

## Decisions to resolve during the prototype

unverified until measured or decided:

- Nautilus thumbnailer versus extension API for arbitrary executable files.
- Whether reliable launcher-to-file matching covers enough apps for the first
  release without a broad remote catalog.
- How strongly filename-only matches should affect displayed artwork: automatic
  for tightly constrained rules, or suggestions requiring a user choice.
- Behavior when a matching desktop entry explicitly names an unavailable icon.
- Which identifiers remain stable across file moves and application updates.
- Implementation language and per-asset licensing/attribution policy.
- Provider coverage and contribution API suitability; whether our Cloudflare
  service is required at launch or only for later missing/custom artwork.
- Exact Cloudflare components, hosting costs, moderation retention, and reviewer
  authentication for reviewers only. Nathan reports Cloudflare should already be
  authenticated (conversation); current access is unverified and should be
  verified when deployment begins. No backend deployment is included in this
  documentation update.

## First implementation slice

Completed in the first native client: an executable with a valid `.desktop`
entry resolves, and catalog artwork can be selected for a file without one.
The original slice was to build a
read-only resolver that explains both outcomes, then make Files display the
resolved icon for the first and a small local catalog icon for the second.
Keep this slice offline and reversible; use it to choose the integration API.
