# Real portable files: useful failures, not a scorecard

`state/portable-coverage.json` and ignored local
`build/portable-fixtures/manifest.json`, acquired 26 September 2026.

The dataset deliberately stays small: current official Linux Godot and Telegram
portable executables, the existing OCCT file, and one misleading-name control.
The reason is to expose a missing product behavior and an unsafe automatic match,
not inflate test counts. None of these executables was run. No production upload
or personal-file icon mutation occurred during acquisition/read-only evaluation.

## What the examples exposed

**Godot showed a real UI false negative.** Its official filename is
`Godot_v4.7.2-stable_linux.x86_64`. The resolver offers Dashboard Icons' `godot`,
but the previous UI initialized search as `Godot_v4.7.2` and displayed zero
matches. The icon already exists upstream; changing the search to `godot` finds
it. The resolver and native chooser now share the same filename hint, so the
initial search offers Godot directly. The actual UI path below verified the fix;
the original read-only baseline remains preserved as defect evidence.

**Telegram has suggestions, not proof of identity.** The real portable Telegram
ELF gets `telegram` suggestions from both providers. A copy of `/usr/bin/true`
named `Telegram` gets the same suggestions. Both score 0.6 and are ineligible for
automatic application at 0.90. The control demonstrates why a plausible filename
must not silently become an authoritative application identity. The user can
still make an explicit choice.

**OCCT is a true upstream coverage miss.** A fresh upstream catalog has no OCCT
suggestion or search match. The separate user-local exact-build mapping remains
useful but is intentionally absent from this clean-provider evaluation. Do not
represent it as generic OCCT support or silently seed it into this baseline.

## Acquisition and local manifest

Godot's [official Linux download page](https://godotengine.org/download/linux/)
listed 4.7.2, released 18 August 2026. Its download endpoint redirected to the
publisher's object storage for the 4.7.2 Linux x86_64 ZIP.
[Telegram Desktop's official site](https://desktop.telegram.org/) links its
Linux x64 endpoint, which redirected to `td.telegram.org`'s 7.2.9 archive.
The exact source/redirect URLs, archive and executable paths, sizes and SHA-256
values are recorded in the ignored manifest. These locally calculated hashes
record the obtained bytes; they are not a publisher-checksum verification.

`tests/integration/acquire_portable_fixtures.py` bounds archive downloads to 300 MB and
extracts only the expected regular executable member, bounded to 1 GB. It checks
ELF magic, never executes the results, and leaves all downloads inside ignored
`build/portable-fixtures`. The one negative control contains `/usr/bin/true`
bytes, also never executed. Acquiring an executable does not establish permission
to redistribute its branding or icons.

A fresh real provider catalog is stored under
`build/portable-fixtures/catalog-cache/app-faces/catalog.json`; it contains no
artwork cache. Source commits for this run:

- selfh.st: `589d718a638b7770abae0edd1b60ff36c0dd1d5a`
- Dashboard Icons: `ab52e3bfaa737cba86793c76ccfcb312f8841278`

`tests/integration/portable_coverage.py` reads that catalog and resolves the loose files
without installed desktop associations. It records the previous UI search formula
explicitly as `legacy_initial_ui_search`, so a later UI fix does not erase the
original defect evidence. Application confidence is separate from whether a
provider happens to have plausible artwork. UI verification belongs to the
parent native test harness, not this report.


## Defect → fix → visible outcome

`state/native-e2e/upstream-result.json` and its local screenshots.
The subsequent real Godot case exposed a second defect: the downloaded PNG and
GVFS metadata were correct, but Nautilus kept showing a generic icon until manual
refresh. A metadata-only assertion would have missed this user-visible failure.

The client now writes a small journaled `user.app-faces.icon` extended attribute
to trigger the file monitor after applying the icon, and restores/removes its
owned marker during Undo. Marker operations are tied to the journaled inode;
later external changes are preserved. This needs a writable file with user-xattr
support. File contents, mode and mtime are preserved; **ctime changes**. If the
marker is unavailable, icon metadata can still be saved and the UI asks the user
to refresh the folder if necessary. It does not falsely guarantee instant visual
refresh on unsupported filesystems.

The official Godot ELF began with an empty artwork cache and a generic Files tile.
The native chooser offered Godot from the pinned Dashboard entry, downloaded the
PNG, and applied bytes matching that normalized upstream artwork. The actual
Nautilus tile then showed the Godot face **without reloading the folder**. Undo
returned it to the generic tile, also without reload. Pixel checks observed no
Godot-art pixels before, 1,143 after Apply and none after Undo; the screenshots
were inspected locally:

- `state/native-e2e/upstream-files-before.png`
- `state/native-e2e/upstream-files-applied.png`
- `state/native-e2e/upstream-files-restored.png`

The background `run_once` scan also abstained from applying an icon to the
misleading Telegram-named control. No downloaded binary was executed, no icon
was uploaded, and no Cloudflare deployment was needed for these local Python
fixes. This proves this real upstream-artwork path in isolated Nautilus/Xvfb;
it does not establish generic app identification or personal Wayland dock grouping.

## Telegram / selfh.st: cancel → reopen → Apply → visible icon → Undo

`state/native-e2e/telegram-selfhst/upstream-result.json` (passed,
26 September 2026), screenshots beside it, and
`state/native-e2e/visual-matcher-regression.json`.

Run `./tests/integration/e2e-telegram.sh` as the desktop user after acquiring the fixtures
and pinned catalog above. It uses the existing private Xvfb/D-Bus wrapper; no
personal desktop input, executable launch, upload or production mutation occurs.
Its state transitions are:

1. A copy of the real Telegram executable starts without custom-icon metadata;
   the artwork cache is empty. An automatic scan abstains on a different file
   containing `/usr/bin/true` bytes under the misleading name `Telegram`.
2. Open the chooser through the real Files script. Its initial search offers the
   pinned selfh.st entry. Select it and wait for the remote preview.
3. Close the preview without Apply. The executable still has no custom icon.
4. Reopen, select the same entry, Apply, and close the chooser. The normalized
   managed PNG must exactly match the downloaded asset. The actual Files tile
   must render the paper-plane artwork without a manual folder reload.
5. Reopen, choose Restore previous, and close. Custom metadata is absent again
   and the rendered upstream artwork disappears. The locally inspected screenshot
   confirms the original generic executable icon is visible again. Cleanup ends
   the private session and removes its temporary file/configuration state.

The first attempt exposed a **test-oracle defect**, not an application defect:
counting the single most frequent exact RGB colour fails on Telegram's gradient
when the icon is downsampled. That original failure and screenshots remain in
`state/native-e2e/telegram-selfhst-exact-rgb-failure/`. The replacement in
`tests/integration/icon_render_match.py` compares the artwork's spatial RGB pattern at
normal Files icon sizes, preserving aspect ratio and excluding transparent
edges. It includes the symbol's white/dark details, so a shared blue background
cannot establish a match. Mean channel error must be at most 12/255 and at least
90% of samples must be within 25/255. Telegram passes at 0.248/255 mean error,
with all 187 sampled pixels within tolerance.

The harness also exposed GTK4 coordinate differences under bare Xvfb: accessibility
reports a tile origin 28 pixels above/left of the screenshot, while the X window
has no client-frame-extents property. The matcher searches a bounded extra
32 pixels around that single-file tile when the property is unavailable; it does
not weaken the image thresholds. When available, actual client shadow extents
are used for coordinate translation. Results record bounds, geometry, matched
position, scale, sample count and errors for diagnosis.

Nine offline checks on saved Godot/Telegram screenshots recognize both applied
icons, reject both before/Undo states, reject each application's icon as the
other, and reject a horizontally mirrored Telegram symbol with the **same colour
palette**. `tests/test_icon_render_match.py` preserves a dependency-light synthetic
regression for gradient artwork, aspect ratio, resize, generic background and
same-palette wrong geometry. It requires system GI/GdkPixbuf, not a display.

For configured providers, the native runner also accepts `--upstream-config`
with a TOML file copied and validated inside its private XDG configuration, and
an arbitrary `--upstream-provider` ID. A matching pinned catalog must be supplied;
no personal upstream configuration is changed by the test.
