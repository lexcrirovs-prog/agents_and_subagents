---
type: shared-team
updated: 2026-04-29
---

# SkillRouting

## Goal

- route business work to the right department first
- keep each agent's skill surface small enough to be reliable
- use peer consultation instead of pretending one agent owns every domain

## Default Routes

- marketing messages, Telegram/MAX/YouTube/site tone -> `marketing`
- contracts, legal clauses, Civil Code risk -> `legal`
- boiler engineering, norms, commissioning, NotebookLM/RAG -> `technical-director`
- production status, warehouse, bottlenecks -> `production`
- Beeline call recordings, transcription, sales scripts -> `sales-lead`
- unclear, strategic, or cross-department executive work -> `main`

## Canonical Storage

- reusable skills belong in `workspace/skills/`
- source-specific examples belong in `client-files/` or runtime memory, not inside generic skill text
- durable cross-agent facts belong in `shared/`
- private working notes stay in each agent's `workspace/memory_system/`

## Agent Usage Rule

- start from `memory_system/profile/SkillRoster.md`
- if the task belongs to another department, ask that department
- if you consulted a peer, mention the peer in the final internal report
