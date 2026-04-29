# Runtime Template

This is the repo-local Ductor home template for `agents_and_subagents`.
It models an enterprise team: the main agent is the director, and sub-agents
act as departments.

## What is included in this baseline

- generic config and `.env` examples
- repo-local bootstrap / doctor / ready-check flow
- bounded tool surface: `task_tools`, `cron_tools`, `webhook_tools`, `agent_tools`
- enterprise skill pack copied from `skills-generic/`
- bundled shared/team layer for roster, handoff, reporting, and memory discipline
- context-hygiene scaffolding in `memory_system/context/`
- seeded `project-vault/` for the director and department structure
- a clean reusable sub-agent seed under `agents/_template/`

## Recommended install

1. Run `python3 ../scripts/subscriber_install.py`
2. Choose provider only if both Codex and Claude are already authenticated
3. Paste the Telegram bot token
4. Send the one-time `/pair CODE` message to the bot from the owner account
5. Let the installer write config, run strict preflight, and auto-start the runtime
6. Copy `agents.example.json` to `agents.json` after filling sub-agent bot tokens
   and allowed user ids
7. Start or restart the runtime so the director can delegate to departments

The installer bootstraps `.venv`, refreshes this template, writes `.env` and
`config/config.json`, binds the real Telegram owner id, and can leave the bot
running immediately after install.

## Maintenance commands

- `../scripts/bootstrap.sh` - refresh template and framework dependencies only
- `../scripts/doctor.sh` - re-run tooling/auth/runtime health checks
- `../scripts/run-main.sh` - start in the foreground when you intentionally use
  `subscriber_install.py --no-start` or want a manual foreground run

## Optional multi-agent scaffold

1. Edit `../agent-templates/team.example.json` if department roles change
2. Run `../scripts/render_agent_templates.py`
3. Copy `agents.example.json` to `agents.json`
4. Fill the matching agent token env vars in `.env`
5. Fill `allowed_user_ids` for the rendered agents before final doctor/start checks
6. After install, create extra departments with `workspace/tools/agent_tools/create_agent.py`

## Rules

- Keep this template generic and self-contained
- Do not add symlinks to external skill stores or sibling/private repos
- Copy this template for client installs; do not point it at any private runtime
