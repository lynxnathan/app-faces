#!/bin/sh
# Real Telegram / selfh.st regression: cancel, Apply, visible Files icon, Undo.
set -eu
cd "$(dirname "$0")/../.."
fixture=build/portable-fixtures/Telegram/Telegram
catalog=build/portable-fixtures/catalog-cache/app-faces/catalog.json
if [ ! -f "$fixture" ] || [ ! -f "$catalog" ]; then
  echo 'Acquire the official portable fixtures and pinned catalog first; see docs/PORTABLE-NEGATIVE-CASES.md.' >&2
  exit 2
fi
exec ./tests/integration/native-e2e.sh \
  --upstream-fixture "$fixture" --upstream-catalog "$catalog" \
  --upstream-slug telegram --upstream-provider selfhst \
  --case-name telegram-selfhst --verify-cancel
