#!/usr/bin/env bash
# Run pi from source with the lane-router extension and keys from .env.
# Usage: ./run.sh [pi args...]   (run from the project directory you want the agent to work in)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
set -a
source "$ROOT/.env"
set +a
exec "$ROOT/vendors/pi/pi-test.sh" --no-extensions -e "$ROOT/extensions/lane-router/index.ts" "$@"
