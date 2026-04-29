---
type: roadmap
updated: 2026-04-22
---

# NextSteps

## Current Queue

1. Finish guided installer flow with minimal required questions
2. Validate Telegram-ready onboarding and post-install smoke checks
3. Keep shared/team, memory, and project-vault layers aligned with the real runtime
4. Expand the specialist layer in a public-safe way without importing private data
5. Validate archive handoff on target platforms

## Platform Rule

- macOS and Linux are first-class targets
- Linux server install is a normal supported path
- Windows should be treated via WSL2 until native support is explicitly proven

## Decision Rule

Do not add a new layer unless it materially improves reliability, operator
clarity, or team coordination.
