# Tools Directory

This is the navigation index for workspace tools.

## Global Rules

- Prefer these tool scripts over manual JSON/file surgery.
- Run with `python3`.
- Normal successful runs are JSON-oriented; tutorial/help output may be plain text.
- Open the matching subfolder `AGENTS.md` before non-trivial changes.

## Routing

- recurring tasks / schedules -> `cron_tools/AGENTS.md`
- incoming HTTP triggers -> `webhook_tools/AGENTS.md`
- file/media processing -> `media_tools/AGENTS.md`
- sub-agent management (create/remove/list/ask) -> `agent_tools/AGENTS.md`
- background tasks (delegate, list, cancel) -> `task_tools/AGENTS.md`
- custom user scripts -> `user_tools/AGENTS.md`

## External API Secrets

External API keys are loaded from `${DUCTOR_HOME:-$HOME/.ductor}/.env` and injected into all
CLI subprocesses (host and Docker). Standard dotenv syntax:

```env
PPLX_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-yyy
export MY_VAR="quoted value"
```

Existing environment variables are never overridden by `.env` values.

## Bot Restart

To restart the bot (e.g. after config changes or recovery):

```bash
touch "${DUCTOR_HOME:-$HOME/.ductor}/restart-requested"
```

The bot picks up this marker within seconds and restarts cleanly.
No tool script needed — just create the file.

## Output and Memory

- Save user deliverables in `../output_to_user/`.
- Update `../memory_system/MAINMEMORY.md` silently for durable user facts/preferences.
