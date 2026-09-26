# “How robust?” “Yes.” — testing while someone uses the computer

This account follows the local development records linked below. The title and
“I was never told what was hard — so I did it” came from the conversation with
Nathan. No attribution to another person is implied.

The user wanted to watch his episode. The test wanted to inspect the dock. Both
had reasons, but only one owned the computer.

App Faces started with a familiar problem: portable Linux applications appear as
gears or generic executables. The proposed behavior was to find artwork in existing
catalogs, respect local choices, suggest uncertain matches and apply sufficiently
supported matches automatically. It also needed to undo its changes.

“The icon was applied” can describe several different events: saving a PNG,
writing metadata, repainting a folder item, installing a launcher, or associating
a running window with the correct dock entry. Those events can disagree.

## Correct file, stale display

The first useful fixture was an official Godot executable named
`Godot_v4.7.2-stable_linux.x86_64`. The catalog contained its icon and the resolver
found the suggestion. The interface's initial search used a different fragment of
the filename and hid the result. Sharing normalization between the resolver and
the interface fixed that path without treating a filename as proof of identity.

A second failure appeared after the correct PNG and GVFS metadata were present:
Nautilus still displayed the generic icon until the folder was refreshed. A test
that stopped at metadata assignment would have accepted the reported defect.

The fix uses the `user.app-faces.icon` extended attribute to emit a file change
notification. The marker is journaled for rollback. Undo checks the recorded inode
and preserves subsequent external edits. File content, permissions and mtime stay
unchanged; ctime changes. When the marker cannot be written, the interface reports
that refreshing the folder may be necessary.

The accepted flow started with a generic icon, downloaded upstream artwork,
displayed Godot without reloading the folder, then restored the generic icon with
Undo. The checks included both bytes and rendered pixels.
See [portable application cases](PORTABLE-NEGATIVE-CASES.md).

## The test also needs validation

Telegram supplied another application, provider and image. Its gradient exposed a
matcher defect: an exact RGB color common in the original PNG does not necessarily
survive scaling. The screen was correct; the acceptance rule was wrong.

The replacement matcher checks spatial arrangement, aspect ratio and light/dark
details using explicit tolerances. Finding blue pixels is insufficient. A mirrored
plane with the same palette must fail. Captures of the initial, applied and restored
states constrain the matcher against accepting unrelated artwork.

GTK4 accessibility coordinates also differed from screenshot coordinates by window
margins. The test now searches a bounded region around the expected file tile.
Searching the entire screen could falsely match the chooser's own preview.

The saved scenario covers Cancel without changing the file, reopening, applying,
visible verification and Undo. A separate control contains `/usr/bin/true` bytes
under the name `Telegram`: it receives suggestions, but automatic assignment
abstains. A plausible name does not authorize a silent change.
See [the Telegram flow and matcher criteria](PORTABLE-NEGATIVE-CASES.md#telegram--selfhst-cancel--reopen--apply--visible-icon--undo).

## Files and dock require separate checks

A custom file icon does not establish a running window's launcher identity. The
dock test observed the identity announced by the application and checked GNOME's
actual association.

Godot ran in both Wayland and XWayland with test configuration. Each flow started
without a matching launcher, checked the generic entry, created the launcher,
found it visually in the overview and activated it. Two windows had to form one
dock entry with the expected icon. Removing the launcher and reopening the app
had to restore the generic baseline.

Observed identities differed: `org.godotengine.ProjectManager` on Wayland and
WM_CLASS `Godot` on XWayland. The record distinguishes Shell widget API activation
from physical pointer input. See [dock acceptance](DOCK-E2E.md).

## A test reached the wrong session

“Allow Remote Interaction” appeared during testing. Tracing identified the local
Xwayland process as the requester. The wrapper started private D-Bus before Xvfb;
a subsequently activated accessibility service inherited the personal display.
Synthetic input reached that Xwayland and triggered the remote interaction portal.

The runner was changed to create the display before the bus, clear inherited bus
addresses and inspect the accessibility service display before generating input.
No RemoteDesktop calls were observed in the subsequent monitored run. That finding
came from tracing the request. The local diagnosis is recorded at
`state/native-e2e/remote-dialog-diagnosis.json`.

## The episode continues

OCCT added a concrete requirement: new SVG and PNG artwork installed persistently
for future launches. App Faces applied the artwork and created `OCCT.desktop`.
Its identity matched the real window's WM_CLASS `OCCT`; Shell referenced the
expected managed PNG.

This exposed a boundary in the earlier Godot test. That test supplied an observed
identity to the launcher API. It proved that a correctly configured launcher
worked; it did not prove that every customized executable already had one. OCCT
still needed that persistent association. The gear seen by the user was a real
failure of the requested experience despite earlier passing tests.

Nathan was watching fullscreen video. The dock actor existed but was not mapped
on screen. A screenshot could establish neither the icon's appearance nor a
product failure. The test now records `desktop-in-use` separately. It does not count
as visual acceptance and does not trigger repeated attempts to take focus.

The solution ran the real OCCT executable in an isolated GNOME session with Ubuntu
Dock and a byte-for-byte copy of the installed `OCCT.desktop`. The XWayland window
announced class `OCCT` and instance `OCCTGUI`. Shell associated it with
`OCCT.desktop`; exactly one mapped dock entry referenced the expected PNG. The
capture showed the new red chip-and-pulse icon. No personal-session input was
required. The local result and image are in `state/occt-isolated-dock/`.

Personal-session association and isolated-session pixel verification are
complementary evidence. The first isolated wrapper passed visual acceptance but
failed while cleaning private FUSE mounts. Cleanup was corrected to unmount only
those resources. The rerun exited successfully without temporary session
directories. The executable hash remained unchanged and the persistent launcher
remained installed. No OCCT update or stress test was triggered.

## State transitions define the coverage

Useful coverage identifies the starting state, trigger, expected change and
invariants. Cancel must not apply. Undo must restore owned changes. Suggestions
must not become identity evidence. A test must detect when its observation is
blocked or belongs to another session.

Dolphin 25.12.3 required Refresh after Apply and Undo to repaint the preview. The
interface reports that requirement. Omitting it from a passing result would hide
work the user still has to do. See [coverage boundaries](../ROADMAP.md).

The intended experience is straightforward: download an application, recognize it,
launch it and undo an icon choice when needed. Sometimes that requires changing
the client; sometimes the observer or test environment. Choosing the right layer
lets the user keep using the computer while the work proceeds—even when he is the
chaos monkey.
