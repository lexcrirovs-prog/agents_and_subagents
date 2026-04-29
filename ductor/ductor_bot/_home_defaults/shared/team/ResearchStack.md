---
type: shared-team
updated: 2026-04-17
---

# ResearchStack

## Baseline For All Codex Agents

- Codex native web search is available in this environment through the built-in web tool; do not add legacy CLI flags such as `--search`.
- Global MCP servers are shared through `~/.codex/config.toml`, so every Codex-based agent can use the same research/browser layer.
- Default policy: use only already-available local, open-source, or browser-native tools unless the user explicitly approves a paid or registration-required service.

## Current Shared MCP Layer

### openaiDeveloperDocs

- Purpose: read-only OpenAI docs search and page access.
- Best for: OpenAI API, Codex, Apps SDK, model/docs questions.
- Source: `https://developers.openai.com/mcp`

### playwright

- Purpose: deterministic browser automation via Playwright MCP.
- Best for: structured navigation, clicking, forms, scraping JS-heavy pages in a controlled browser.
- Strength: LLM-friendly structured interaction, good default browser tool.

### chrome-devtools

- Purpose: live Chrome automation and debugging through Chrome DevTools MCP.
- Best for: real Chrome debugging, network/performance inspection, screenshots, browser-state-sensitive work.
- Strength: strongest option when a normal browser context matters.

## Research Routing

### Quick factual research

- Use Codex native web search first.
- Fetch and compare primary sources before answering.

### OpenAI / Codex / API docs

- Prefer `openaiDeveloperDocs` MCP first.

### Structured browser tasks

- Prefer `playwright` MCP first.

### Live browser debugging or browser-state-sensitive tasks

- Prefer `chrome-devtools` MCP.

## Rule

- Do not jump to browser automation for simple questions that native search can answer.
- Do not rely on social chatter for technical truth when official docs exist.
- For research deliverables, keep sources and claims separated.
- Do not introduce new paid tools, API subscriptions, or account-creation requirements without explicit approval.
