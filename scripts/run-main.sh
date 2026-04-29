#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/_runtime_env.sh
source "$ROOT_DIR/scripts/_runtime_env.sh"

cd "$ROOT_DIR"
exec "$ROOT_DIR/.venv/bin/ductor" "$@"
