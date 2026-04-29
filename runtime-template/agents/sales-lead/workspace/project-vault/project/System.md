---
type: project
status: active
updated: 2026-04-29
---

# System

## Goal

Ship an install-safe Telegram-first enterprise multi-agent system built on
`ductor`, where the main agent acts as director and sub-agents act as business
departments with their own skills, memory, schedules and source boundaries.

## Baseline Included

- director runtime
- five department sub-agent templates
- install-local shared/team layer
- private per-agent memory
- task / cron / webhook tooling
- agent creation and inter-agent delegation
- project-vault seed for architecture and role ownership
- example source configuration files under `client-files/`

## What This Vault Is For

- track install-local system shape
- record operator-facing decisions
- keep the roadmap and architecture truthful
- document which sources are connected and which are still placeholders

## Rule

This vault must stay install-local and operator-safe. Source data belongs here
only after the operator deliberately adds it to this install.
