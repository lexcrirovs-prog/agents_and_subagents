---
type: shared-team
updated: 2026-04-29
---

# ReportingProtocol

## Default Report Shape

Every substantial report should prefer this order:

1. Task
2. Findings
3. Conclusion
4. Risk
5. Next move

## Reporting To The User

- speak plainly
- give the answer before the background
- do not expose internal agent chatter unless it matters to the decision
- ask for approval before sending messages, publishing posts, or committing legal/business actions

## Reporting To The Director

- return `DONE`, `PARTIAL`, or `BLOCKED`
- say which departments were consulted
- include only the facts that matter for command and next action
- separate confirmed source facts from assumptions

## Memory Writeback Rule

- before reporting substantial work as `DONE`, perform the silent writeback required by `shared/team/MemoryProtocol.md`
- if a durable fact or open loop remains only in chat, the task is not actually finished

## Delegated Task Status

For delegated sub-agent work, the user-facing owner chat should expose:

- `ACCEPTED`
- `BLOCKED`
- `DONE`

The final substantive answer still comes from the current visible owner.
