# Tools Directory

This is the navigation index for the public baseline tools.

## Global Rules

- Prefer these tool scripts over manual JSON/file surgery.
- Run with `python3`.
- Open the matching subfolder `AGENTS.md` before non-trivial changes.

## Routing

- sub-agent management and delegation -> `agent_tools/AGENTS.md`
- recurring tasks / schedules -> `cron_tools/AGENTS.md`
- incoming HTTP triggers -> `webhook_tools/AGENTS.md`
- background tasks -> `task_tools/AGENTS.md`

Not bundled in this baseline: `media_tools`, `user_tools`.

## External API Secrets

External API keys are loaded from `${DUCTOR_HOME:-$HOME/.ductor}/.env` and
injected into CLI subprocesses when present.

## Bot Restart

To restart the bot after config/runtime changes:

```bash
touch "${DUCTOR_HOME:-$HOME/.ductor}/restart-requested"
```

## Output and Memory

- Save user deliverables in `../output_to_user/`.
- Keep durable user/runtime facts in `../memory_system/`.
