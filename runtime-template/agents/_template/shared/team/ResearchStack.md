---
type: shared-team
updated: 2026-04-29
---

# ResearchStack

## Baseline

- use already-available local files and connected source exports first
- prefer official documentation when technical, legal, or API truth matters
- keep sources and claims separated in research deliverables
- do not introduce paid or registration-required research services without explicit approval

## Source Boundaries

- Telegram/MAX/YouTube/site facts require connected exports, APIs, or user-provided files
- NotebookLM/RAG facts require an exported or locally queryable knowledge base
- Beeline call facts require recording export access and call metadata
- production facts require the current production status file
- legal checks require the actual document text and jurisdiction/context

## Routing

- quick factual research -> native web search
- official product/API docs -> official documentation or source sites
- source archive analysis -> local files under `client-files/` or runtime memory
- live browser/API debugging -> deterministic browser automation or connector-specific tools
