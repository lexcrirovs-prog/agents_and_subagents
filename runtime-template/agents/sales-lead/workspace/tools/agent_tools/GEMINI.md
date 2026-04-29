# Agent Tools

Public-safe tools for inter-agent communication and local sub-agent registry
management.

## Available Tools

- `ask_agent.py` - sync request to another agent
- `ask_agent_async.py` - async handoff to another agent
- `create_agent.py` - create a Telegram sub-agent from the local clean template
- `remove_agent.py` - remove a sub-agent from `agents.json` while preserving its home
- `list_agents.py` - show configured sub-agents and their key settings

## Rules

- `create_agent.py`, `remove_agent.py`, and `list_agents.py` are main-runtime tools.
- Bot tokens must stay env-backed (`env:...`), not hardcoded into `agents.json`.
- The clean reusable seed lives under `agents/_template/`.
- The reply from `ask_agent.py` or `ask_agent_async.py` returns to the calling
  agent, not directly to the target bot's own chat.
