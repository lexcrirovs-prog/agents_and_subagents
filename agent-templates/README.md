# Enterprise Agent Templates

This directory is the source of truth for the `agents_and_subagents` department
layer.

## Purpose

- define install-safe department roles
- render `runtime-template/agents.example.json`
- scaffold isolated sub-agent homes under `runtime-template/agents/<name>/`
- keep the director/sub-agent structure reproducible

## Current Departments

- `marketing` - content, style learning, Telegram/MAX/YouTube/site publications
- `legal` - contracts, Civil Code risk, organization interests
- `technical-director` - boiler engineering, NotebookLM/RAG, standards, commissioning
- `production` - production state, warehouse, stage velocity, bottlenecks
- `sales-lead` - Beeline call exports, transcription, sales script quality

## Render

```bash
python3 scripts/sync_runtime_template.py
python3 scripts/render_agent_templates.py
```

Then copy `runtime-template/agents.example.json` to
`runtime-template/agents.json`, fill `allowed_user_ids`, and provide the token
environment variables from `.env.example`.

## Rules

- no secrets in this manifest
- no personal archives inside templates
- source-specific examples belong in `client-files/`
- each role should stay narrow enough that peer consultation remains useful
