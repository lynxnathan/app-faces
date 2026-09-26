# Development and configuration

For installation, use the [README](README.md#install). Commands below run as the desktop user.

## Setup

This setup installs development tools. Python 3.14+, uv, distribution PyGObject/GTK4/GdkPixbuf/GVFS and systemd user session.
`unsquashfs` enables nonexecuting Type2 AppImage extraction. Node24+ supports the
strict TypeScript Cloudflare backend. GTK bindings intentionally use distribution
system site packages; Python tooling is locked in `uv.lock`, backend in package-lock.

```sh
./scripts/setup.sh
./scripts/check.sh
python3 install.py
```

The installation is user-local and points to this checkout. Reinstall after moving
it. Optional onboarding shows installed icons with every sharing checkbox empty.
Skipping does not affect local recognition. No backend URL means no contributions.

## Automatic recognition

Precedence: existing custom icon, exact desktop entry, embedded Type2 AppImage
artwork, optional known SHA256, AppStream name evidence, provider name suggestion.
Desktop entries use GLib parsing and XDG override rules, including Hidden tombstones
and NoDisplay. Shell/Flatpak/Snap/Wine wrappers remain unresolved; no program or
Exec string is executed for identity detection. Ambiguous desktop entries block
automatic assignment. Missing desktop artwork does not authorize provider fallback.

The user timer runs about once a minute; scans skip files modified within15seconds,
scan depth2, at most10,000 entries/2,000 candidates and3 remote artwork requests.
Scores are heuristic rules, not measured probability: exact desktop/bundle/hash1.0,
unique exact catalog slug plus AppImage magic0.92, plain names0.60, threshold0.90.
AppStream binary names are suggestions. Undo opts that inode out of automatic work.

Caches include positive/negative identity results and stat-keyed hashes. File,
catalog, desktop metadata, AppStream or icon-theme changes invalidate recognition.
Owned automatic icons may refresh; manual changes remain authoritative. Move
tracking uses inode/device when a missing old path is encountered. Source images
are normalized and copied into content-addressed local storage before application.

Config: `$XDG_CONFIG_HOME/app-faces/config.json`, normally `~/.config/app-faces/config.json`:

```json
{
  "directories": ["/absolute/path/to/portable-apps"],
  "automatic_enabled": true,
  "community_url": "https://your-worker.example"
}
```

All keys optional. Default folders: Downloads, Desktop (localized XDG names too),
Applications, .local/bin, plus existing launcher targets under home. Network work
retrieves public catalog metadata and selected asset IDs; local file paths, launch
commands and executable hashes are not sent. Public providers refresh daily;
community catalog refreshes every5minutes. Offline caches remain usable.

## CLI and recovery

```sh
app-faces resolve /absolute/path/to/app
app-faces resolve /absolute/path/to/app --sha256
app-faces apply /absolute/path/to/app --icon /path/to/icon.svg
app-faces undo /absolute/path/to/app
app-faces pause
app-faces resume
app-faces rollback
app-faces uninstall
python3 install.py --uninstall --keep-icons
```

`apply --replace` is required to replace an existing custom icon. The chooser's
Apply button is an explicit replacement. Rollback pauses automatic application,
stops the active scanner, restores owned icons and removes unedited generated
launchers. Uninstall first stops/disables services, then rolls back and removes
only manifest-owned unchanged integration files. Changed files and missing targets
are reported. Corrupt journals fail closed. Cached artwork/journals are retained
because preserved choices may still refer to them; no global caches are deleted.
`--keep-icons` is an explicit uninstall exception. `--no-service-start` supports
packaging/tests without a live desktop service manager.

Data: `$XDG_DATA_HOME/app-faces` contains changes/launcher/install journals, local
artwork, outbox receipts and last-run report. `$XDG_CACHE_HOME/app-faces` contains
provider metadata, revision history, fingerprint and recognition caches.

```sh
app-faces add-launcher /absolute/path/app --name Example --icon /path/icon.png
app-faces add-launcher /absolute/path/app --name Example --icon /path/icon.png --app-id org.example.App
app-faces remove-launcher /absolute/path/to/generated.desktop
app-faces catalog --import-file /path/to/catalog.json
app-faces catalog --revision SHA256_REVISION
```

Use an app ID/WM class actually supplied by the app; generated launcher IDs cannot
invent Wayland window identity. Existing matching launchers are reused and never
rewritten. The Files icon and Shell launcher are separate integration paths.

## Optional contributions and backend

Only explicit selected onboarding rows or unchecked-by-default Upload when Apply
can enqueue icons. Payloads contain app ID/name, normalized PNG, source, license
and variant; never raw desktop entries, local paths, Exec, accounts or fingerprints.
Retries preserve a random idempotency key. Local Apply succeeds independently of
submission delivery. Unresolved licenses remain pending until moderator correction.

```sh
app-faces outbox
app-faces submission RECEIPT_ID
app-faces submission RECEIPT_ID --action cancel
app-faces submission RECEIPT_ID --action retry
```

Cancellation applies to unsent queued items. Already submitted proposals use their
private receipt for review status/correction feedback. Reviewers revoke published
artwork in the dashboard. No contributor login exists.

See [backend/README.md](backend/README.md) for local dev, production provisioning,
reviewer tokens, roles, rate limits, deployment and teardown. A local endpoint
`http://127.0.0.1:8787` is accepted for development. Production requires HTTPS.
Production is deployed on Workers Free with D1 only. See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for the URL, auth and verification.

## KDE and verification

[adapters/kde/README.md](adapters/kde/README.md) documents the compiled Qt6/KF6
thumbnail bridge. Install the optional plugin with:

```sh
python3 install.py --kde-plugin /absolute/path/libappfacesthumbnail.so --qt-plugin-dir "$HOME/.local/lib/qt6/plugins"
```

Choose a plugin root already discoverable by your Qt6 installation; installer does
not alter the environment. Dolphin previews must be enabled. No plugin is installed
by default on GNOME. Optional plugin ownership participates in uninstall.

`./scripts/check.sh` runs Ruff, strict mypy across all Python modules, and pytest.
`cd backend && npm ci && npm run check && npm run format:check` validates strict
TypeScript and real Worker/D1 integrations. Native plugin has CTest coverage.
`tests/integration/integration.py` verifies real GVFS apply/undo; `tests/integration/ui_smoke.py` renders
the GTK window locally. `tests/integration/community_integration.py` exercises Python→Worker
approval/revocation against the local server using synthetic data and temporary XDG
folders. No screenshots are uploaded.

### Moderation interface

`backend/src/ui.ts` contains the accessible page structure, `admin.styles.ts` the
styles and `admin.ts` the interactions. `npm run check:all` runs strict type checks,
backend integration tests and Firefox UI flows. Install the test browser with
`npx playwright install firefox`. Run desktop tests as the normal user.

See [MODERATION-FLOWS.md](docs/MODERATION-FLOWS.md) for scenarios, states,
invariants and boundaries. `e2e/production-smoke.mjs` is an explicit read-only
check of the deployed endpoint, outside the local suite. Reports and screenshots
remain local.

### Native E2E display isolation: diagnosed incident and correction

local `state/native-e2e/remote-dialog-diagnosis.json`,
`remote-portal-trace.log`, and `remote-portal-after-fix.log` (26 September 2026,
01:25 America/Sao_Paulo). The locally retained screenshot `remote-dialog.png`
shows GNOME's **Remote Desktop / Allow Remote Interaction** permission dialog.
It has not been uploaded or published.

The trace records RemoteDesktop `CreateSession`, `SelectDevices` and `Start`
from bus sender `:1.830`. `busctl status` identified that sender as the personal
session's `/usr/bin/Xwayland`, PID 5335, display `:0`, with `-enable-ei-portal`.
This was a test-isolation failure: the wrapper started its private D-Bus **before**
Xvfb, so the accessibility service activated by that bus inherited the personal
DISPLAY. Synthetic pointer input through `Atspi.generate_mouse_event` reached
that Xwayland and triggered its input-emulation portal request. The evidence
identifies this local path; it does not establish an incoming RDP connection or
an attack.

The corrected wrapper is `tests/integration/native-e2e.sh`. It clears inherited
`WAYLAND_DISPLAY`, `DBUS_SESSION_BUS_ADDRESS` and `AT_SPI_BUS_ADDRESS`, starts
**Xvfb first**, then starts the private D-Bus session inside that environment.
The active native flow uses `xdotool` on the isolated DISPLAY for pointer input,
with AT-SPI reserved for reading/bound actions. Never reverse that launch order
or substitute the earlier experimental `tests/integration/native_flow.py` input path.

The subsequent portal monitor captured **no RemoteDesktop method calls during
the next test runs** (`remote-portal-after-fix.log`). This verifies the observed
regression window, not permanent absence of all possible input-routing defects.
Personal keyboard activity should remain on the personal display. Diagnosis and
isolation repair are complete. Subsequently, the integrated native UI/cloud flow
passed all nine checks in `state/native-e2e/result.json`: real Files/GTK, native
file selection and Apply/Undo, explicit upload, Firefox production approval,
background sync/digest-verified download, second-file native consumption and Undo,
and browser revocation observed by the client. This is Xvfb/private-D-Bus evidence,
not personal Wayland dock acceptance. Fixtures only; no executable was launched
and screenshots remain local.

### Focused native regressions

Run as the desktop user. `tests/integration/native-e2e.sh --isolation-only` validates both
the Xvfb server and the activated accessibility service before any input;
`--components` runs the GTK component cases inside the same private environment.
The public-contribution journey requires `--endpoint`, `--moderator-file` and Node
on PATH (or `--node`); it uses only synthetic artwork and revokes publication.

The real upstream case needs no moderator credentials or Node:

```sh
./tests/integration/native-e2e.sh \
  --upstream-fixture build/portable-fixtures/Godot/Godot_v4.7.2-stable_linux.x86_64 \
  --upstream-catalog build/portable-fixtures/catalog-cache/app-faces/catalog.json
```

It starts with an empty artwork cache, requires the initial chooser to offer Godot,
checks downloaded/applied bytes, and checks the rendered file tile before/after
Apply and Undo without reloading Files. It also runs automatic matching on an
unrelated ELF named Telegram and requires it to remain unchanged. No downloaded
executable is run and no upstream artwork is uploaded. The bounded fixture
acquisition and expected misses are documented in `docs/PORTABLE-NEGATIVE-CASES.md`.

### Personal-session dock regression

The explicit [dock E2E guide](docs/DOCK-E2E.md) describes the saved two-driver
Godot flow, bounded Shell observer, setup, cleanup and evidence. Unlike the isolated
Files test, this opens real application windows in the personal GNOME session and
checks the actual dock actor. It is not run by headless CI or the normal check script.

### Configured upstreams and file lifecycle regressions

[UPSTREAMS.md](docs/UPSTREAMS.md) documents validated TOML sources, adapters and
source lifecycle. `tests/integration/e2e-configured-upstream.sh` syncs a new source namespace
and runs real Files Cancel/Apply/Undo with its artwork. It changes no personal
source configuration. `PYTHONPATH=. python3 tests/integration/file-lifecycle-e2e.py` exercises
real GVFS moves, replacements and user-edit preservation in disposable directories
with the actual background scanner; its ELF fixtures are never executed.

### Isolated application dock test

```sh
tests/integration/isolated-app-dock.sh \
  /absolute/path/org.example.App.desktop org.example.App \
  /absolute/path/expected.png /absolute/path/local-results
```

This launches the supplied application in a headless GNOME Shell with Ubuntu Dock,
a private D-Bus session and temporary XDG directories. Supply its observed window
class; the runner checks window/launcher association, one mapped dock entry and
screenshot pixels against the supplied PNG. It does not inject input into the
personal session. Use disposable application data when testing a real application.
The runner isolates desktop state, not the application's access to the host.

To create a launcher for the generic GTK fixture:

```sh
mkdir -p build/dock-fixture
cat > build/dock-fixture/org.example.App.desktop <<EOF
[Desktop Entry]
Type=Application
Name=Dock fixture
Exec=/usr/bin/python3 "$PWD/tests/fixtures/desktop_app.py" --app-id org.example.App
Icon=$PWD/tests/fixtures/artwork/processor.png
StartupWMClass=org.example.App
EOF
tests/integration/isolated-app-dock.sh \
  "$PWD/build/dock-fixture/org.example.App.desktop" org.example.App \
  "$PWD/tests/fixtures/artwork/processor.png" "$PWD/state/generic-dock"
```

`tests/fixtures/desktop_app.py` creates only the test window. `tests/fixtures/artwork/processor.png` supplies generic
artwork. Historical OCCT runs are recorded in the roadmap; no vendor-specific
artwork or executable mapping ships with the application.

## Local evidence

Test reports, screenshots and desktop session data are written under `state/` and
excluded from Git. Run the documented checks to generate local evidence.


[Test quality and targeted mutation checks](docs/TEST-QUALITY.md) documents what the assertions prove and their limits.
