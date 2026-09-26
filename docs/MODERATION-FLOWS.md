# Moderation flows

The web suite runs Firefox through Playwright against the built Worker and an
isolated Miniflare D1 database. Business operations use the real backend. Recovery
tests inject a 503 before an operation or abort a request; these are controlled
failures, not infrastructure outages.

Run `npm run test:ui` in `backend`. Install the test browser with
`npx playwright install firefox`. `npm run check` checks four strict TypeScript
configurations and backend integration tests. Screenshots remain local under
`state/`; production credentials do not participate in the local suite.

| Flow | Transitions | Verified behavior |
| --- | --- | --- |
| Login | locked → invalid password → recoverable error | Password preserved; reveal/hide works; invalid credentials do not grant access. |
| Publication | pending → review → 503 → retry → approved → restored → revoked | Reason survives failure; approval persists in D1; history and logout work. |
| Repeated correction | pending → cancel → pending → correction → correction → rejected | Cancel writes nothing; each decision increments the version and records its reason. |
| Read recovery | connected → network failure → retry → readable queue | Visible error and recovery action. |
| Reviewer role | authenticated → versions/review → Escape | Administrator controls absent; Escape closes without a decision. |
| Resubmission conflict | correction → contributor resubmits → stale review → withdrawal | Stale version cannot overwrite; withdrawal visible; receipt remains private. |
| Merge | proposal → invalid target → corrected draft → merged | Draft preserved; artwork published under the existing identity. |
| Lost response | approval committed → response aborted → refresh | Committed state reconciled without repeating the write. |
| Reauthentication | draft → expired session → wrong password → valid password → resume | Draft preserved; no automatic decision submission. |
| Layout and accessibility | login, queue, review and decision at desktop/mobile widths | No horizontal overflow; centered dialogs; actions remain in the viewport; automated axe WCAG A/AA checks. |
| Delayed artwork | open review before download → image decoded | Submitted preview updates without reopening; absent catalog icon stays distinct. |
| Keyboard navigation | review → decision → Escape → review → Escape → queue | Focus returns to the initiating control; history, versions and sign-out remain reachable at 320px. |

Each scenario owns its fixtures and does not depend on another scenario succeeding.
The correction cycle is observed for two transitions; the workflow is not required
to terminate after those transitions.

## Native integration

The separate native flow opens the chooser from real Files, applies a synthetic
icon without sharing, and restores it. It then submits a pending contribution
with explicit consent. Firefox approves it in production; the client observes
approval, synchronizes the catalog and downloads the artwork. A second file finds,
applies and undoes that icon. Firefox revocation then appears in the client.

Nautilus, GTK and Firefox run under Xvfb with a private D-Bus session. The backend
is the deployed Worker. Nine integration checks passed. Fixtures are synthetic;
no application executable was started and no screenshot was uploaded. This flow
is separate from personal Wayland dock grouping and portable application coverage.

A test isolation bug once triggered GNOME's remote interaction dialog: the private
D-Bus session started before Xvfb, allowing accessibility activation to inherit the
personal display. The runner now creates the display first, clears inherited bus
addresses and checks the accessibility service display. No RemoteDesktop calls
were observed during the subsequent monitored run. See [development](../DEVELOPMENT.md).

## Boundaries

The original nine Firefox scenarios are not exhaustive state-machine coverage.
Version conflict after a concurrent update is covered; sustained load with many
moderators and manual screen-reader navigation are not. Automated axe checks do
not replace manual accessibility review. Six separate production client/API
checks covered correction and withdrawal without uploading personal icons; those
checks do not establish GTK interface behavior.

Language-specific checks are documented in [I18N.md](I18N.md).
