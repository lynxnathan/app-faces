#!/bin/sh
# Run as the desktop user; GTK/GIO remain provided by the distribution.
set -eu
cd "$(dirname "$0")/.."
if [ "$(id -u)" -eq 0 ]; then
  echo 'Run this setup as your normal desktop user.' >&2
  exit 1
fi
./scripts/setup.sh
cd backend
npm ci
npx playwright install firefox
