#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/_runtime_env.sh
source "$ROOT_DIR/scripts/_runtime_env.sh"

cd "$ROOT_DIR"

echo "== Tooling =="
python3 --version
node --version
npm --version
codex --version
if command -v claude >/dev/null 2>&1; then
  claude --version
else
  echo "claude: not installed"
fi

echo
echo "== Ductor auth view =="
"$ROOT_DIR/.venv/bin/python" - <<'PY'
from ductor_bot.cli.auth import check_claude_auth, check_codex_auth, check_gemini_auth

for result in (check_codex_auth(), check_claude_auth(), check_gemini_auth()):
    print(f"{result.provider}: {result.status.value}")
PY

echo
echo "== Config file =="
echo "$DUCTOR_HOME/config/config.json"

echo
echo "== Runtime preflight =="
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/preflight_runtime.py" --home "$DUCTOR_HOME"

echo
echo "== Internal API ready =="
if [[ -f "$DUCTOR_HOME/bot.pid" ]]; then
  if "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/wait_runtime_ready.py" --home "$DUCTOR_HOME" --timeout 2 --quiet; then
    echo "main runtime is ready"
  else
    echo "main runtime is not ready"
  fi
else
  echo "bot.pid not found"
fi
