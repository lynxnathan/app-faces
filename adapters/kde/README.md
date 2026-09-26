# Dolphin adapter (KF6 / Qt6)

The Python resolver is shared with GNOME. Dolphin previews use the native
`KIO::ThumbnailCreator` interface; GVFS custom-icon metadata is not a KDE
file-icon API. We never write a `.directory` file for individual executables.

The service-menu installer in the main installation puts **App Faces** in
Dolphin's context menu. It launches the same icon chooser. Explicit choices are
stored in the app-owned journal; the thumbnail bridge reads that journal before
resolving known applications. Unknown/ambiguous files have no generated preview.
No network traffic and no application execution occurs during a thumbnail request.

## Build

Dependencies: CMake >=3.25, a C++20 compiler, Qt6 >=6.6, ECM and KF6 KIO/CoreAddons
>=6.0 development packages. These are supported minimums, not pinned old releases;
build with the current distribution packages. PyGObject/GdkPixbuf are also needed.

```sh
cmake -S adapters/kde -B build/kde -DCMAKE_INSTALL_PREFIX="$HOME/.local"
cmake --build build/kde
ctest --test-dir build/kde --output-on-failure
```

Use the application installation manager for a reversible copy of the built
plugin into the actual Qt6 plugin search directory. The compiled helper path
points at this checkout by default; package builds must set `APP_FACES_HELPER`
to the installed helper location. Do not relocate the checkout afterward.

Dolphin must have previews enabled for **App Faces application artwork**.
This supplies previews, not unconditional decoration when previews are disabled.
Thumbnail disk caching is disabled. Correction/undo is reflected after Dolphin’s
Refresh action (F5); a journal-only change does not invalidate an already visible
preview automatically. The chooser explains this after Apply and Undo.

Validation (2026-09-25): native plugin compiled with GCC 15.2, Qt 6.10.2 and
KF6 6.24.0. CTest `kde_plugin_roundtrip` passed: dynamically loads the plugin,
resolves a fixture desktop entry, calls the Python helper, checks its 64×32 PNG,
and rejects remote/missing inputs. Fourteen Python launcher/bridge tests passed.
Dependencies were downloaded using apt's verified download-only mode and
extracted under ignored `build/kde-deps`; no system package was installed.

Live Dolphin preview/menu behavior was subsequently verified under isolated Xvfb (see below). The native test
validates the plugin boundary, not the running Dolphin UI. The build artifact
from this validation depends on KF6 runtime libraries in that extracted tree;
do not distribute it as a self-contained binary.

Sources (official):
- https://api.kde.org/kio-thumbnailcreator.html
- https://api.kde.org/kio-thumbnailrequest.html
- https://develop.kde.org/docs/apps/dolphin/service-menus/

## Isolated live-test runtime (prepared 26 September 2026)

Dolphin 25.12.3 and its missing runtime dependencies were downloaded through
APT's verified **download-only** mode, then extracted into `build/kde-deps/root`.
The download log is `build/kde-deps/dolphin-download.log`. The machine's package
database still has no installed `dolphin` or `libkf6kiogui6` package. No default
file manager, KDE session, or personal Dolphin settings were changed.

`isolated-dolphin.sh --prepare` creates disposable HOME/config/data/cache under
ignored `build/dolphin-session` without launching anything. `--launch [folder]`
opens an actual window and must be coordinated with other desktop automation.
It supplies the compiled plugin and extracted KF6 libraries, uses a private
D-Bus session to avoid reusing another Dolphin process, and explicitly silences
audio. The graphical display/runtime socket still comes from the real user
session. The helper and plugin remain tied to this checkout. Cleanup consists
of closing the test process and removing its disposable build directory.

The runtime's initial headless `--version` command passed; `ldd` reported no missing
Dolphin libraries and `kde_plugin_roundtrip` passed again. These do **not** claim
that a Dolphin window has rendered a preview or that its context menu worked.

## Compatibility matrix

| Surface | Verified local version | Evidence / boundary |
| --- | --- | --- |
| GNOME Shell | 50.1 | Installed package; main project covers actual GNOME user session |
| Nautilus | 50.2.2 | Installed package; GVFS icon integration is separate from KDE previews |
| Qt Core / QPA | 6.10.2 | Installed Qt runtime; extracted matching Qt libraries used as needed |
| Qt Wayland | 6.10.2 | Installed platform plugin available; no graphical test in this preparation step |
| KDE Frameworks / KIO | 6.24.0 | Extracted verified distribution packages; native plugin roundtrip passed |
| Dolphin | 25.12.3 | Extracted executable starts headlessly; live preview/menu/chooser verified below |
| KDE Plasma session | Not tested | No Plasma session installed or started for this test |
| Qt 5 / KF5 Dolphin | Unsupported by this adapter | Native plugin builds against Qt6/KF6 only |
| Other distribution versions | Unverified | Build minimums are not a tested support matrix |

On either desktop, application identity and available artwork remain separate
from how the desktop chooses to present them. Dolphin previews require previews
enabled and the App Faces thumbnail provider selected; a compiled plugin alone
cannot demonstrate this user-visible path.


## Live isolated Dolphin UI evidence (26 September 2026)

`state/dolphin-live-e2e.json` and local screenshots
`state/dolphin-preview.png`, `state/dolphin-menu.png`, and
`state/dolphin-chooser.png`. The script is `adapters/kde/tests/live_e2e.py`.

A real Dolphin 25.12.3 window rendered the synthetic executable's bright green
artwork through the native thumbnail provider (3,364 exact-color screen pixels).
Its context menu displayed App Faces, and activating that entry opened the real
GTK chooser for the same fixture with the same artwork. The fixture is a copy
of `/usr/bin/true` associated with a disposable desktop entry; it is never run.
No upload or real user file icon change occurs.

The missing `thumbnail` KIO worker initially blocked previews. Download-only
`kio-extras` 25.12.3 supplied it; extracted runtime dependencies are therefore
required in addition to Dolphin itself. The fixture enables both possible
plugin IDs (`appfacesthumbnail` / `libappfacesthumbnail`) to accommodate the
current build's library-name discovery. No system package was installed.

Isolation uses an Xvfb display, private D-Bus, explicit X11 for both Qt and GTK,
an invalid Wayland socket, disposable HOME/config/data/cache, and silent audio
endpoints. Physical typing on the personal desktop cannot reach this display.
The preview toggle uses AT-SPI. This Qt build does not expose its dynamically
created context-menu item in the accessible tree, so that one action uses a
coordinate verified in the immediately preceding local screenshot; successful
opening of the expected chooser verifies its effect. That fallback is specific
to this fixed test viewport and is not claimed as a universal robust selector.

The extended flow now covers preview → context menu → chooser → cancel → reopen
→ choose different local image → Apply → Dolphin Refresh → Undo → Dolphin Refresh.
The initial green preview contains 3,364 green pixels. Applied magenta artwork
contains 3,364 magenta pixels, then Undo removes the magenta preview. The journal
entry is checked at Apply and removed at Undo; cancellation creates no entry.
File bytes, executable mode and nanosecond mtime remain unchanged. Screenshots
must settle with the file tile present, so a transient empty folder cannot pass
an absence assertion. Undo suppresses automatic resolution for that file, leaving
the generic executable icon rather than immediately reinstating the inferred
preview. The fixture is never executed and sharing stays unchecked.

Additional local evidence: `state/dolphin-cancelled.png`,
`state/dolphin-apply-notice.png`, `state/dolphin-before-refresh.png`,
`state/dolphin-applied.png`, `state/dolphin-restored.png`.
This does not claim testing of KDE Plasma shell/dock integration or other
Dolphin versions. `automatic_refresh: false` is recorded explicitly.

### Why Refresh is needed

Observed in Dolphin 25.12.3/KIO 6.24.0: changing our private journal does not
change the file properties compared by KIO. A standard `FilesChanged` D-Bus
signal also leaves the current preview unchanged. There were no thumbnail
cache files to invalidate (`CacheThumbnail=false`). The relevant upstream
implementation re-stats an item and only emits a change when
[`KFileItem::cmp` differs](https://github.com/KDE/kio/blob/master/src/core/kcoredirlister.cpp);
the comparison includes mode/size/mtime but not our journal or xattr
([comparison source](https://github.com/KDE/kio/blob/master/src/core/kfileitem.cpp)).
We preserve executable contents and timestamps and show the concrete F5 action.
An automatic refresh mechanism is future integration work; this E2E verifies
that the documented user recovery action really redraws Apply and Undo.

```sh
./adapters/kde/tests/live-e2e.sh
```

Always wrap the launch with the required `agent-silent` runner. Use a real user
session transport if running from a root agent namespace.

The wrapper establishes private HOME/XDG/runtime and GTK portal selection before
starting D-Bus, and disables GVFS FUSE mounts. The test seeds an empty fresh
catalog so this local-artwork flow does not fetch upstream data.
