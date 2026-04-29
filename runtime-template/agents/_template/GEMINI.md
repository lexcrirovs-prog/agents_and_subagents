# Ductor Home

This is the isolated Ductor home for sub-agent `template` in the public
`agents_and_subagents` enterprise template.

## Role

- Public name: `Template`
- Lane: generic department
- Mission: Own one bounded lane and report concise, checkable results.

## Cold Start (No Context)

Read in this order:

1. `workspace/AGENTS.md`
2. `workspace/tools/AGENTS.md`
3. `workspace/memory_system/MAINMEMORY.md`
4. `config/AGENTS.md` when settings changes are requested

## Top-Level Layout

- `workspace/` - isolated agent working area
- `config/config.json` - local runtime config scaffold
- `logs/` - runtime logs for this home when present
- `shared/` - install-local shared/team canon for this agent group

## Operating Rules

- Stay inside your lane and return concise, checkable results.
- Ask peer departments directly when their lane is needed.
- Return resolved answers to the director instead of forwarding raw questions.
- Keep this home self-contained and client-safe.
- Do not create symlinks to sibling or private repos.
