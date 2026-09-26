#!/bin/sh
# Same-format source under a new ID: configuration -> sync -> actual Files Apply/Undo.
set -eu
cd "$(dirname "$0")/../.."
test "$(id -u)" != 0 || { echo 'Run as the desktop user' >&2; exit 1; }
case_root="$PWD/build/configured-upstream-e2e"
mkdir -p "$case_root/config/app-faces" "$case_root/cache"
cat > "$case_root/config/app-faces/upstreams.toml" <<'EOF'
[[sources]]
id = "selfhst"
enabled = false

[[sources]]
id = "dashboard"
enabled = false

[[sources]]
id = "selfhst-mirror"
repository = "selfhst/icons"
format = "selfhst"
ref = "589d718a638b7770abae0edd1b60ff36c0dd1d5a"
priority = 50
EOF
XDG_CONFIG_HOME="$case_root/config" XDG_CACHE_HOME="$case_root/cache" \
  PYTHONPATH="$PWD" /usr/bin/python3 -m app_faces.cli sync
exec ./tests/integration/native-e2e.sh \
  --upstream-fixture build/portable-fixtures/Telegram/Telegram \
  --upstream-catalog "$case_root/cache/app-faces/catalog.json" \
  --upstream-config "$case_root/config/app-faces/upstreams.toml" \
  --upstream-slug telegram --upstream-provider selfhst-mirror \
  --case-name configured-selfhst-mirror --verify-cancel
