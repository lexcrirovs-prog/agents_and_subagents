---
type: shared-team
updated: 2026-04-22
---

# MemoryProtocol

## Principle

- substantial work is not finished until memory triage is complete
- durable context should not remain only in chat
- shared facts go to `shared/`; private working memory stays in each agent's
  `workspace/memory_system/`
- write signal, not sludge

## Silent Memory Triage

Before the final answer on substantial work, check these routes in order:

1. durable user fact or preference -> `shared/` or private `memory_system/profile/`
2. team rule, roster fact, handoff rule, system fact -> `shared/team/`
3. project state, ownership, decision, next step -> private project/decision notes
4. meaningful same-day progress -> `memory_system/daily/YYYY/MM/YYYY-MM-DD.md`
5. open loop that must survive the session -> `memory_system/context/`

If none of these changed, write nothing.

## Anti-Patterns

- do not leave durable facts only in chat history
- do not dump everything into `MAINMEMORY.md`
- do not duplicate the same fact in shared and private memory without reason
