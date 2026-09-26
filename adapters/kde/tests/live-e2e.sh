#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
task_session=$(mktemp -d /tmp/app-faces-dolphin.XXXXXX)
trap 'rm -rf "$task_session"' EXIT HUP INT TERM
export HOME="$task_session/home" XDG_CONFIG_HOME="$task_session/config" XDG_DATA_HOME="$task_session/data" XDG_CACHE_HOME="$task_session/cache" XDG_RUNTIME_DIR="$task_session/runtime"
mkdir -p "$HOME" "$XDG_CONFIG_HOME/xdg-desktop-portal" "$XDG_DATA_HOME" "$XDG_CACHE_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
cat > "$XDG_CONFIG_HOME/xdg-desktop-portal/portals.conf" <<'PORTAL'
[preferred]
default=gtk
org.freedesktop.impl.portal.FileChooser=gtk
PORTAL
unset DBUS_SESSION_BUS_ADDRESS AT_SPI_BUS_ADDRESS WAYLAND_DISPLAY
export APP_FACES_ISOLATED_DISPLAY=1 GDK_BACKEND=x11 XDG_SESSION_TYPE=x11 GVFS_DISABLE_FUSE=1 GTK_USE_PORTAL=0
export PULSE_SERVER=unix:/nonexistent/app-faces-audio PIPEWIRE_REMOTE=/nonexistent/app-faces-audio
xvfb-run -a dbus-run-session -- /usr/bin/python3 adapters/kde/tests/live_e2e.py
