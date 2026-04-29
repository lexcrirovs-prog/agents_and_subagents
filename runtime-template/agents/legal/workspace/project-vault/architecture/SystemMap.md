---
type: architecture
updated: 2026-04-29
---

# SystemMap

## Contours

- `workspace/project-vault/` - install-local project and architecture vault
- `workspace/memory_system/` - private operating memory for the director
- `shared/` - install-local cross-agent canon
- `agents/<name>/workspace/memory_system/` - private memory per department
- `workspace/tools/` - task, cron, webhook, and inter-agent control surface
- `client-files/` - examples and source-export landing zones

## Runtime Model

- user-facing primary transport: Telegram
- chief/orchestrator: `main` as director
- departments: `marketing`, `legal`, `technical-director`, `production`, `sales-lead`
- collaboration: departments ask each other through inter-agent tools before reporting upward
- operator path: local `Codex` or `Claude Code` drives install and maintenance

## Memory Model

- shared facts for the team -> `shared/`
- private working memory -> each agent's `memory_system/`
- architecture / roadmap / system decisions -> `project-vault/`
- session continuity / reset hygiene -> `memory_system/context/`
- raw source exports -> `client-files/` or external source connectors

## Source Model

- marketing sources: Telegram, MAX, YouTube, website exports
- legal sources: contracts and organizational policy
- technical sources: NotebookLM/RAG, standards, chats, designer correspondence
- production sources: production status files and warehouse data
- sales sources: Beeline call exports, `transkrib_prog`, scripts

## Growth Rule

New agents should:

- inherit the install-local shared/team layer
- receive their own private memory
- join the existing delegation model instead of inventing a parallel one
- declare source boundaries before claiming source awareness
