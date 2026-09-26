# Real GNOME dock acceptance — 26 September 2026

saved result (`../state/dock-e2e/result.json`, local),
[runner](../tests/integration/dock-live-e2e.py) and
[Shell observer](../tests/integration/dock-probe.js). Both Godot cases passed in Nathan's
actual GNOME Shell 50.1 session with Ubuntu Dock, not in Xvfb.

## What was exercised

The official Godot 4.7.2 portable executable previously acquired for the Files
regression was **executed in this test**, as an unprivileged user. No project was
opened. Test wrappers supplied separate XDG config/data/cache directories, the
chosen display driver, OpenGL compatibility rendering and a dummy audio driver.
The wrappers exec the real binary; they are the targets of the generated launchers.
The earlier Files test remains a separate, nonexecuting test.

For each display driver, the runner:

1. Opens the project manager without a matching desktop entry. The actual Shell
   window tracker reports a `window:…` association and the dock actor uses
   `application-x-executable`. This is the negative baseline.
2. Reads the window's actual identity and closes that owned process.
3. Calls App Faces `add_launcher` with the observed identity and the locally stored
   Godot artwork obtained from the pinned Dashboard upstream in the earlier test.
   This flow tests launcher consumption of existing managed artwork, not another
   download or filename-based identity inference.
4. Waits for both the desktop search index and Shell's application registry to
   discover the launcher. It then opens the actual overview, enters the test query,
   requires one mapped visual result with the expected icon and emits its click signal
   to launch the first window. Gio DesktopAppInfo launches a second window.
5. Checks two real windows map to the same expected desktop entry and exactly one
   mapped dock actor represents both. Both the app icon and the actor's rendered
   GIcon reference the expected managed PNG. Local screenshots were inspected and
   show the Godot face in the dock, with no second generic Godot entry.
6. Closes only test-owned processes, calls App Faces `remove_launcher`, and waits
   for the entry to disappear from search, Shell lookup and the running dock. It
   repeats the query in the visual overview and confirms that result is absent.
7. Reopens the same binary without its launcher and verifies the generic window
   association and icon return. Closes that final test process.

| Driver | Observed identity | Created and removed entry | Outcome |
| --- | --- | --- | --- |
| Native Wayland | `org.godotengine.ProjectManager` | `org.godotengine.ProjectManager.desktop` | Two windows, one correct dock icon; removal/reopen restores generic baseline |
| X11 through XWayland | WM_CLASS `Godot`, instance `Godot_ProjectList` | `Godot.desktop`, StartupWMClass `Godot` | Same accepted lifecycle |

Screenshots and intermediate snapshots are local under `state/dock-e2e/`; the
result records the exact stage names that identify the corresponding PNG files.
Screenshots are ignored by git and must not be uploaded or published automatically.
Both generated desktop files were confirmed absent after the run. Test configuration
and evidence remain under ignored build/local state paths; normal App Faces artwork
cache retention still applies. Existing launchers/favorites were not changed.

## Scope and remaining work

This establishes actual launcher-to-window association, displayed dock artwork,
multiwindow grouping and owned-launcher removal for this Godot build in both display
modes. It does not establish that arbitrary portable apps announce usable identities,
that a filename can identify an app, or that Files metadata alone controls the dock.
The negative baseline is absence of a matching launcher, not a deliberately spoofed
identity collision. Search registry discovery/removal and the actual visible overview result/click
are exercised. Query entry and button click are dispatched through Shell widget APIs,
not physical keyboard/pointer input. Pin/unpin favorites,
editing existing user launchers, session restart and Plasma dock remain separate.

No product code fix was needed for the two accepted dock cases. The observer's
initial use of a nonexistent `Shell.AppSystem.search` method was corrected to the
desktop search API before the accepted run. This was test instrumentation, not
evidence of a product failure. Deprecated Gio DesktopAppInfo references in the
saved harness were replaced by their GioUnix namespace equivalent and the extended
visual-search flow passed with those changes. The search observer follows GNOME
50's actual AppIcon actors, not the generic SearchResult class used by other providers.

## Explicit rerun in a personal desktop

This opt-in regression opens real windows; it is not part of headless unit CI.
Run the Python runner as the desktop user. It requires the official Godot fixture,
the saved upstream PNG, GNOME/Ubuntu Dock, GI GioUnix and a functioning Looking Glass.
It refuses preexisting colliding launcher IDs through App Faces' ownership checks.

1. Create `state/dock-e2e` and remove an old `request.json` from that directory
   before starting a new observer. Do not run two instances concurrently.
2. In GNOME Looking Glass (Alt+F2, `lg`), import the absolute local module and call
   `run` with the absolute evidence directory, substituting this checkout's path:

   ```js
   import('file:///ABSOLUTE/CHECKOUT/tests/integration/dock-probe.js').then(m => m.run('/ABSOLUTE/CHECKOUT/state/dock-e2e'))
   ```

3. Close Looking Glass, then from this checkout run:

   ```sh
   python3 tests/integration/dock-live-e2e.py
   ```

4. Inspect `state/dock-e2e/result.json` and the captured images. The runner requests
   observer shutdown in its finalizer; the observer also stops itself after ten
   minutes. Manual shutdown, if the runner is interrupted, uses
   `{"stage":"stop-complete","stop":true}` in its request file. The observer has no D-Bus service
   or arbitrary command execution endpoint and does not enable Shell unsafe mode.

The recorded host run bootstrapped Looking Glass with the existing linux-setup
temporary-keyboard utility under root, then ran the applications and runner as
the desktop user. Root was used for that bounded input device only, not to run
Godot. It did not use the RemoteDesktop portal or alter firewall/session services.

## Concurrent personal desktop use

A hidden dock (for example behind fullscreen playback) is not an icon failure.
The runner waits for the target actor to be mapped; if foreground activity prevents
visual acceptance, it records `disposition: desktop-in-use`, `productFailure: false`
and exits 77, with normal owned-fixture cleanup. Interrupted visual acceptance is
not a passing visual test either. Headless/private-display regressions remain the
repeatable CI path; personal-session runs must not fight the user for focus.
