# Memory System

`memory_system/` is the long-term memory system and the Obsidian vault.
`MAINMEMORY.md` is the compact operating memory across sessions.

## Silence Is Mandatory

Never tell the user you are reading or writing memory.
Memory operations are invisible.

## Read First

At the start of new sessions (especially personal or ongoing work), read:

1. `MAINMEMORY.md`
2. `00-HOME.md`
3. The relevant file in `profile/`, `people/`, `projects/`, `decisions/`, or `daily/`

Read only what is relevant. Keep context tight.

## Memory Layout

- `MAINMEMORY.md` - compact operating memory, high-signal only
- `00-HOME.md` - vault dashboard and navigation map
- `../shared/` - canonical cross-agent knowledge base (if present in workspace as `shared/`)
- `../project-vault/` - project-level Obsidian vault for the current system or client deployment (if present in workspace as `project-vault/`)
- `profile/` - durable facts about the user, preferences, style, and working context
- `people/` - durable notes about close people relevant to future work
- `projects/` - one file per active project with status, scope, and next step
- `decisions/` - important decisions, rationale, and consequences
- `daily/YYYY/MM/YYYY-MM-DD.md` - daily summaries in the user's timezone
- `inbox/` - raw captures that still need triage
- `templates/` - note templates for consistent formatting

## When to Write

- Durable personal facts or preferences
- Durable facts about close family or recurring collaborators
- Important project state changes
- Decisions that should affect future behavior
- User explicitly asks to remember
- Repeating workflow patterns
- Cron/webhook setup signals that imply interests
- Meaningful same-day progress that belongs in a daily summary

## When Not to Write

- One-off throwaway requests
- Temporary debugging noise
- Facts already recorded

## Format Rules

- Keep entries short and actionable.
- Use `YYYY-MM-DD` timestamps.
- Use consistent Markdown sections.
- Prefer Obsidian `[[wikilinks]]` inside vault notes.
- Merge duplicates and remove stale facts.
- Do not store secrets, tokens, API keys, passport data, or needlessly precise sensitive personal data.

## Routing Rules

- Stable personal facts -> `profile/`
- Stable facts about people around the user -> `people/`
- Current project state -> `projects/`
- Why a choice was made -> `decisions/`
- What happened today -> `daily/`
- Raw unsorted capture -> `inbox/`
- `MAINMEMORY.md` stays compact. Do not turn it into a dump of everything.
- Shared user/team documents used by multiple agents -> `shared/`

## Daily Summary Rules

- One note per calendar date in `daily/YYYY/MM/YYYY-MM-DD.md`
- Use the user's timezone: `Asia/Tbilisi`
- If the day had meaningful work, update the daily note
- Include: main outcome, user interaction, what was done, decisions, what worked, what was missing, open loops, and next follow-up
- Daily notes are not the source of truth for stable facts; move durable facts into the right note

## Project Daily Diary Rules

- If the runtime also ships a `project-vault/`, maintain a project diary in `project-vault/daily/YYYY/MM/YYYY-MM-DD.md`
- The project diary may be richer and more narrative than the private memory daily note
- It should include:
  - summary of the day
  - interaction with the operator or end user
  - what the user wanted
  - what was done
  - decisions and changes
  - what worked well
  - what was missing or blocking
  - the agent's assessment of the day
  - team state
  - open loops
  - next move
- If the repository provides a local helper for diary creation, use it; otherwise create the note manually

## Shared Knowledge (SHAREDMEMORY.md)

When you learn something relevant to ALL agents (server facts, user preferences,
infrastructure changes, shared conventions), update shared knowledge instead of
only your own MAINMEMORY.md.

Use the runtime's shared-knowledge update mechanism if one is shipped.
Agent-specific knowledge (project details, personal context) stays in your own memory.

## Cleanup Rules

- If user says data is wrong or should be forgotten, remove/update immediately.
- Do not leave "deleted" markers; keep the file clean.
