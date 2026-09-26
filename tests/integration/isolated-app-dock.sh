#!/bin/sh
set -eu
test "$(id -u)" != 0 || { echo 'Run as the desktop user' >&2; exit 1; }
cd "$(dirname "$0")/../.."
project_root="$PWD"
test "$#" -eq 4 || { echo "Usage: $0 DESKTOP_FILE WM_CLASS EXPECTED_PNG OUTPUT_DIRECTORY" >&2; exit 2; }
launcher_source=$(readlink -e -- "$1")
export APP_FACES_PROOF_DESKTOP_ID APP_FACES_PROOF_WM_CLASS APP_FACES_PROOF_ARTWORK APP_FACES_PROOF_OUTPUT
APP_FACES_PROOF_DESKTOP_ID=$(basename -- "$launcher_source")
APP_FACES_PROOF_WM_CLASS="$2"
APP_FACES_PROOF_ARTWORK=$(readlink -e -- "$3")
APP_FACES_PROOF_OUTPUT=$(readlink -m -- "$4")
test -f "$launcher_source"
proof_root=$(mktemp -d -t app-faces-dock-shell-XXXXXXXX)
cleanup() {
  cleanup_status=$?
  fusermount3 -uz "$proof_root/runtime/doc" 2>/dev/null || true
  fusermount3 -uz "$proof_root/runtime/gvfs" 2>/dev/null || true
  rm -rf -- "$proof_root"
  if [ -f "$APP_FACES_PROOF_OUTPUT/result.json" ]; then
    /usr/bin/python3 -c 'import json,sys; from pathlib import Path; p=Path(sys.argv[1]); r=json.loads(p.read_text()); r.update(cleanupVerified=True,exitCode=int(sys.argv[2])); p.write_text(json.dumps(r,indent=2)+"\n")' "$APP_FACES_PROOF_OUTPUT/result.json" "$cleanup_status"
  fi
  return "$cleanup_status"
}
trap cleanup EXIT HUP INT TERM
export APP_FACES_PROOF_VERIFIER="$project_root/tests/integration/verify_app_dock.py"
mkdir -p "$APP_FACES_PROOF_OUTPUT"
rm -f "$APP_FACES_PROOF_OUTPUT/result.json"
export APP_FACES_PROOF_ICON
APP_FACES_PROOF_ICON=$(/usr/bin/python3 -c 'from gi.repository import GioUnix; import sys; print(GioUnix.DesktopAppInfo.new_from_filename(sys.argv[1]).get_icon().to_string())' "$launcher_source")
# Isolate desktop configuration, data, cache and IPC; preserve the user's HOME.
export XDG_CONFIG_HOME="$proof_root/config" XDG_DATA_HOME="$proof_root/data"
export XDG_CACHE_HOME="$proof_root/cache" XDG_RUNTIME_DIR="$proof_root/runtime"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR" "$XDG_DATA_HOME/applications"
chmod 700 "$XDG_RUNTIME_DIR"
cp "$launcher_source" "$XDG_DATA_HOME/applications/$APP_FACES_PROOF_DESKTOP_ID"
cmp "$launcher_source" "$XDG_DATA_HOME/applications/$APP_FACES_PROOF_DESKTOP_ID"
extension_dir="$XDG_DATA_HOME/gnome-shell/extensions/app-faces-dock-proof@local"
mkdir -p "$extension_dir"
cp tests/integration/dock-extension/metadata.json tests/integration/dock-extension/extension.js "$extension_dir/"
unset DISPLAY WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS AT_SPI_BUS_ADDRESS SESSION_MANAGER
export XDG_DATA_DIRS=/usr/local/share:/usr/share XDG_SESSION_TYPE=wayland
export XDG_CURRENT_DESKTOP=GNOME GNOME_SHELL_SESSION_MODE=user GVFS_DISABLE_FUSE=1
export APP_FACES_PRIVATE_SHELL=1 LIBGL_ALWAYS_SOFTWARE=1
export PULSE_SERVER=unix:/nonexistent/app-faces-audio PIPEWIRE_REMOTE=/nonexistent/app-faces-audio
export ALSA_CONFIG_PATH="$proof_root/alsa.conf"
printf 'pcm.!default { type null }\n' > "$ALSA_CONFIG_PATH"
dbus-run-session -- /bin/sh -eu -c '
  gsettings set org.gnome.shell enabled-extensions "[\"ubuntu-dock@ubuntu.com\", \"app-faces-dock-proof@local\"]"
  gsettings set org.gnome.shell favorite-apps "[]"
  gsettings set org.gnome.desktop.interface enable-animations false
  gsettings set org.gnome.desktop.session idle-delay 0
  gsettings set org.gnome.shell.extensions.dash-to-dock dock-position BOTTOM
  gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed true
  gsettings set org.gnome.shell.extensions.dash-to-dock extend-height false
  gsettings set org.gnome.shell.extensions.dash-to-dock show-trash false
  gsettings set org.gnome.shell.extensions.dash-to-dock show-mounts false
  gnome-shell --headless --wayland --virtual-monitor=1280x900 --mode=user > "$APP_FACES_PROOF_OUTPUT/shell.log" 2>&1 &
  shell_pid=$!
  trap "kill $shell_pid 2>/dev/null || true" EXIT HUP INT TERM
  count=0
  while [ ! -f "$APP_FACES_PROOF_OUTPUT/result.json" ]; do
    kill -0 "$shell_pid"
    count=$((count + 1))
    test "$count" -lt 110
    sleep 1
  done
  /usr/bin/python3 "$APP_FACES_PROOF_VERIFIER" "$APP_FACES_PROOF_OUTPUT" "$APP_FACES_PROOF_ARTWORK"
'
