# Ductor Home

This is the repo-local Ductor home for the `agents_and_subagents` enterprise
team template.

## Cold Start (No Context)

Read in this order:

1. `workspace/AGENTS.md`
2. `workspace/tools/AGENTS.md`
3. `workspace/memory_system/MAINMEMORY.md`
4. `workspace/memory_system/context/` for live handoff state when present
5. `config/AGENTS.md` when settings changes are requested

## Top-Level Layout

- `workspace/` - main working area (tools, memory, cron tasks, skills, files)
- `config/config.json` - runtime configuration
- `logs/` - runtime logs
- `shared/` - bundled generic team docs and install-local shared knowledge
- `workspace/project-vault/` - install-local project/architecture vault seed

## Baseline Shape

- This baseline ships as a director runtime plus department sub-agent tooling.
- The shared/team layer defines the enterprise roster, handoff rules, reporting,
  and memory discipline inside this install.
- External source connectors are configured through env vars, exports, or local
  files; do not invent source facts before they are connected.
- Skills are bounded by `workspace/memory_system/profile/SkillRoster.md` and
  real local directories in `workspace/skills/`.

## Operating Rules

- Use tool scripts in `workspace/tools/` for task, cron, and webhook lifecycle
  changes.
- Keep the runtime self-contained: no symlinks to private repos, sibling
  folders, or global skill stores.
- Save user-facing generated files in `workspace/output_to_user/`.
- Update only requested keys in `config/config.json`.
