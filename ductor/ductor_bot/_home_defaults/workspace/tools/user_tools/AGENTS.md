# User Tools

Create custom scripts here when the user needs one-off or reusable utilities.

## Rules

- Keep scripts in this directory (do not scatter across workspace).
- Reuse existing scripts before creating new ones.
- Use clear filenames and add `--help`.
- Prefer structured stdout (JSON) where practical.
- Remove obsolete scripts when they are no longer useful.

## Python Environment

For dependencies, use a local virtual environment in this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Long Tasks

Avoid blocking chat for long operations.
If needed, run background jobs (for example with `nohup`) and give the user
clear progress/check commands.

## Current Utilities

```bash
python3 tools/user_tools/memory_index.py rebuild --require-embeddings
python3 tools/user_tools/memory_index.py status
python3 tools/user_tools/memory_index.py search "memory architecture"
```

- `memory_index.py` builds one shared runtime SQLite/FTS index over Markdown memory.
- When `OPENAI_API_KEY` is configured, `search` uses hybrid ranking by default:
  `75% semantic embeddings + 25% lexical`.
- The indexed corpus is curated: service docs like `README.md`, `AGENTS.md`,
  prompt mirrors, `templates/`, `context/`, and project `references/` are excluded.
- The database is shared for the whole runtime; access is separated by scope, not by per-agent databases.

## Memory

When creating scripts that indicate recurring user workflows or preferences,
update `memory_system/MAINMEMORY.md` silently.
