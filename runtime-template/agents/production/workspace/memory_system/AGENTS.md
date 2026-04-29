# Memory System

`memory_system/` is the local long-term memory for this install.
`MAINMEMORY.md` is the compact operating memory across sessions.

## Silence Is Mandatory

Never tell the user you are reading or writing memory.

## Read First

1. `MAINMEMORY.md`
2. `00-HOME.md`
3. The relevant note in `profile/`, `people/`, `projects/`, `decisions/`, or `daily/`
4. `context/SESSION_STATE.md`, `context/OPEN_LOOPS.md`, and
   `context/RECENT_DECISIONS.md` for long-running or restart-sensitive work
5. `../project-vault/` when system architecture, install flow, or roadmap state
   matters

## What Belongs Here

- durable user and project facts for this install
- important decisions and rationale
- recurring workflow preferences
- daily summaries and project state
- compact session handoff state in `context/`

## What Does Not Belong Here

- secrets, tokens, API keys
- transient debugging noise
- copied notes from another runtime
- one-off throwaway requests

## Daily Note Rule

Use one note per calendar day in the configured user timezone, and move stable
facts out of daily logs into typed notes.

## Context Hygiene Rule

Keep `context/SESSION_STATE.md`, `OPEN_LOOPS.md`, and `RECENT_DECISIONS.md`
short and factual. They exist to survive resets, restarts, or long-running
install/operator work without dragging raw chat history around.
