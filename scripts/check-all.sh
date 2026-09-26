#!/bin/sh
# Complete local verification. Production and interactive desktop tests are explicit.
set -eu
cd "$(dirname "$0")/.."
./scripts/check.sh
cd backend
npm run check:all
npm run format:check
