---
type: roadmap
updated: 2026-04-29
---

# NextSteps

## Current Queue

1. Fill Telegram bot tokens for the director and five department agents
2. Copy `runtime-template/agents.example.json` to `runtime-template/agents.json`
3. Fill `allowed_user_ids` for each department
4. Connect or export source data for Telegram, MAX, YouTube, site, NotebookLM/RAG, Beeline and production files
5. Configure recurring jobs for marketing posts and sales-call quality reports
6. Validate inter-agent handoff: director -> department -> peer department -> director

## Platform Rule

- macOS and Linux are first-class targets
- Linux server install is a normal supported path
- Windows should be treated via WSL2 until native support is explicitly proven

## Decision Rule

Do not add a new integration layer until the current export/API path and
approval boundary are clear.
