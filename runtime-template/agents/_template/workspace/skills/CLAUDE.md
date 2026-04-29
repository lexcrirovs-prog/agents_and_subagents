# Skills Directory

This public template keeps skills self-contained and bounded.

## Rules

- Real local directories in this folder are the canonical installed skills.
- `memory_system/profile/SkillRoster.md` is the allow-list for the runtime
  skill surface.
- Do not add symlinks to `~/.claude`, `~/.codex`, `~/.gemini`, or sibling repos.
- If you add a vetted skill, copy it in as a real directory and update the
  local `SkillRoster.md`.

## Structure

Each skill lives in its own subdirectory:

```text
skills/my-skill/SKILL.md
```

Optional helpers can live in `scripts/`, `references/`, and other nested files.
