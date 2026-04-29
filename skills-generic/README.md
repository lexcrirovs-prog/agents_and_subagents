# Enterprise Skills Pack

This directory is the source of truth for bundled skills in
`agents_and_subagents`.

## Included Skills

- `enterprise-collaboration` - peer-first department handoff
- `marketing-content-ops` - style learning and publication preparation
- `legal-contract-review` - contract risk review and suggested edits
- `technical-director-knowledge` - boiler, standards, commissioning and RAG use
- `production-bottleneck-analysis` - production files, stock and bottlenecks
- `sales-call-quality` - Beeline calls, transcription and script compliance
- `systematic-debugging` - technical debugging discipline
- `writing-plans` - executable plans for technical and business work

## Rules

- Each skill must be a real local directory.
- No symlinks to private or global skill stores.
- No source exports, tokens, client secrets, or private chats in skill files.
- `scripts/sync_runtime_template.py` copies these skills into
  `runtime-template/workspace/skills/` and writes the matching `SkillRoster.md`.
