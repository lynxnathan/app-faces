#!/bin/sh
# Real native UI, private input/display/bus/storage. Explicit production fixture test.
set -eu
test "$(id -u)" != 0 || { echo 'Run as the desktop user' >&2; exit 1; }
APP_FACES_E2E_ROOT=$(mktemp -d -t app-faces-native-e2e-XXXXXXXX)
export APP_FACES_E2E_ROOT
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-${XDG_CACHE_HOME:-$HOME/.cache}/ms-playwright}"
cleanup() {
  fusermount3 -uz "$APP_FACES_E2E_ROOT/runtime/doc" 2>/dev/null || true
  fusermount3 -uz "$APP_FACES_E2E_ROOT/runtime/gvfs" 2>/dev/null || true
  rm -rf -- "$APP_FACES_E2E_ROOT"
}
trap cleanup EXIT HUP INT TERM
export XDG_CONFIG_HOME="$APP_FACES_E2E_ROOT/config"
export XDG_DATA_HOME="$APP_FACES_E2E_ROOT/data"
export XDG_CACHE_HOME="$APP_FACES_E2E_ROOT/cache"
export XDG_RUNTIME_DIR="$APP_FACES_E2E_ROOT/runtime"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
mkdir -p "$XDG_CONFIG_HOME/xdg-desktop-portal"
cat > "$XDG_CONFIG_HOME/xdg-desktop-portal/portals.conf" <<'EOF'
[preferred]
default=gtk
org.freedesktop.impl.portal.FileChooser=gtk
EOF
export APP_FACES_ISOLATED_DISPLAY=1 GDK_BACKEND=x11 GTK_USE_PORTAL=0 GSK_RENDERER=cairo XDG_SESSION_TYPE=x11
export GVFS_DISABLE_FUSE=1
export PULSE_SERVER=unix:/nonexistent/app-faces-audio PIPEWIRE_REMOTE=/nonexistent/app-faces-audio
unset WAYLAND_DISPLAY DBUS_SESSION_BUS_ADDRESS AT_SPI_BUS_ADDRESS
cd "$(dirname "$0")/../.."
export PYTHONPATH="$PWD"
xvfb-run -a -s '-screen 0 1440x1200x24' dbus-run-session -- \
  /usr/bin/python3 tests/integration/native_flow_e2e.py "$@"
