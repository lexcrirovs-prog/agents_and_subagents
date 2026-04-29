#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
export ROOT_DIR

export DUCTOR_HOME="${ANTIBIOTIK_OPEN_DUCTOR_HOME:-$ROOT_DIR/runtime-template}"
export DUCTOR_FRAMEWORK_ROOT="${ANTIBIOTIK_OPEN_FRAMEWORK_ROOT:-$ROOT_DIR/ductor}"

load_runtime_dotenv_if_present() {
  local env_file="$1"
  [[ -f "$env_file" ]] || return 0

  while IFS= read -r assignment; do
    [[ -n "$assignment" ]] || continue
    export "$assignment"
  done < <(
    python3 - "$env_file" <<'PY'
import os
import shlex
import sys
from pathlib import Path

for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if line.startswith("export "):
        line = line[7:].strip()
    if "=" not in line:
        continue
    key, value = line.split("=", 1)
    key = key.strip()
    if not key or key in os.environ:
        continue
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    print(f"{key}={shlex.quote(value)}")
PY
  )
}

load_runtime_dotenv_if_present "$DUCTOR_HOME/.env"
