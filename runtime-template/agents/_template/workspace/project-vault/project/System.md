---
type: project
status: active
updated: 2026-04-22
---

# System

## Goal

Ship an install-safe Telegram-first multi-agent system built on `ductor` plus a
local CLI operator (`Codex` or `Claude Code`), with durable memory, controlled
delegation, and a clean operator workflow.

## Baseline Included

- main runtime
- install-local shared/team layer
- private per-agent memory
- task / cron / webhook tooling
- agent creation and inter-agent delegation
- project-vault seed for architecture and roadmap tracking

## What This Vault Is For

- track install-local system shape
- record operator-facing decisions
- keep the roadmap and architecture truthful

## Rule

This vault must stay generic and install-local. No personal source-runtime data
belongs here unless the local operator created it inside this install.
