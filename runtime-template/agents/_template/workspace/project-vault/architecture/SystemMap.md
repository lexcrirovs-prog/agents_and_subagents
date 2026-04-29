---
type: architecture
updated: 2026-04-22
---

# SystemMap

## Contours

- `workspace/project-vault/` - install-local project and architecture vault
- `workspace/memory_system/` - private operating memory for the main agent
- `shared/` - install-local cross-agent canon
- `agents/<name>/workspace/memory_system/` - private memory per specialist
- `workspace/tools/` - task, cron, webhook, and inter-agent control surface

## Runtime Model

- user-facing primary transport: Telegram
- chief/orchestrator: `main`
- specialists: install-local sub-agents with separate homes and shared team rules
- operator path: local `Codex` or `Claude Code` drives install and maintenance

## Memory Model

- shared facts for the team -> `shared/`
- private working memory -> each agent's `memory_system/`
- architecture / roadmap / system decisions -> `project-vault/`
- session continuity / reset hygiene -> `memory_system/context/`

## Growth Rule

New agents should:

- inherit the install-local shared/team layer
- receive their own private memory
- join the existing delegation model instead of inventing a parallel one
