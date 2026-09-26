#!/bin/sh
# Launch only on explicit test coordination: opens a real desktop window.
set -eu
project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
runtime_root="$project_root/build/kde-deps/root/usr"
session_root="$project_root/build/dolphin-session"
case "${1:-}" in
  --prepare) ;;
  --launch) ;;
  *) echo 'Usage: isolated-dolphin.sh --prepare | --launch [fixture-directory]' >&2; exit 2 ;;
esac
mkdir -p "$session_root/home" "$session_root/config" "$session_root/data" "$session_root/cache" "$session_root/fixtures"
if [ ! -x "$runtime_root/bin/dolphin" ]; then
  echo 'Extract the verified Dolphin runtime under build/kde-deps/root first.' >&2; exit 1
fi
if [ ! -f "$session_root/config/dolphinrc" ]; then
  cat > "$session_root/config/dolphinrc" <<'EOF'
[General]
ShowFullPath=true
ShowToolTips=true
[PreviewSettings]
Plugins=appfacesthumbnail
EOF
fi
if [ "$1" = --prepare ]; then
  echo "$session_root"
  exit 0
fi
fixture_root=${2:-"$session_root/fixtures"}
[ -d "$fixture_root" ] || { echo 'Fixture directory does not exist.' >&2; exit 1; }
exec /usr/local/bin/agent-silent env \
  HOME="$session_root/home" \
  XDG_CONFIG_HOME="$session_root/config" \
  XDG_DATA_HOME="$session_root/data" \
  XDG_CACHE_HOME="$session_root/cache" \
  XDG_DATA_DIRS="$runtime_root/share:/usr/local/share:/usr/share" \
  XDG_CURRENT_DESKTOP=KDE \
  LD_LIBRARY_PATH="$runtime_root/lib/x86_64-linux-gnu" \
  QT_PLUGIN_PATH="$project_root/build/kde/plugins:$runtime_root/lib/x86_64-linux-gnu/qt6/plugins:/usr/lib/x86_64-linux-gnu/qt6/plugins" \
  PATH="$runtime_root/bin:$runtime_root/lib/x86_64-linux-gnu/libexec/kf6:$PATH" \
  PULSE_SERVER=unix:/nonexistent/app-faces-audio \
  PIPEWIRE_REMOTE=/nonexistent/app-faces-audio \
  /usr/bin/dbus-run-session -- "$runtime_root/bin/dolphin" --new-window "$fixture_root"
