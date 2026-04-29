# Validation Matrix

This checklist validates `agents_and_subagents` before using it as the working
enterprise agent runtime.

## Scope

Validate the real archive artifact, not only the source repo:

```bash
python3 scripts/build_subscriber_kit.py
cd dist/subscriber-kit
```

Primary targets:

- macOS
- Linux desktop / Linux server
- Windows via WSL2

Native Windows is not a promised parity path until separately smoke-tested.

## Fast Gate

Run these first:

```bash
python3 scripts/subscriber_install.py --help
python3 scripts/subscriber_install.py --bootstrap-only
python3 scripts/render_agent_templates.py
```

Expected:

- help renders normally
- `.venv` is created
- editable `ductor` install succeeds
- `runtime-template/` refresh completes
- `runtime-template/agents.example.json` contains the five department agents

## Full Install Gate

Run from a fresh copy of `dist/subscriber-kit`:

```bash
python3 scripts/subscriber_install.py
```

Provide:

- provider choice only if both Codex and Claude are authenticated
- Telegram bot token for the director
- timezone if auto-detected value is wrong

Expected:

1. Installer validates the Telegram token with `getMe`.
2. Installer shows the bot username.
3. Installer asks for owner pairing only through Telegram `/pair CODE`.
4. Pairing captures the real `owner user id`.
5. Installer writes `.env` and `runtime-template/config/config.json`.
6. Strict preflight passes.
7. Runtime auto-starts unless `--no-start` was used.
8. Telegram readiness ping arrives to the paired owner account.

## Department Gate

After install:

1. Copy `runtime-template/agents.example.json` to `runtime-template/agents.json`.
2. Fill each department's `allowed_user_ids`.
3. Fill department token env vars in `.env`.
4. Restart runtime.
5. Run the agent list command or health check.

Expected:

- `marketing`, `legal`, `technical-director`, `production`, and `sales-lead`
  are registered
- `workspace/tools/agent_tools/ask_agent.py` can send a test message to a
  department
- a department can consult another department and report back to `main`

## Source Gate

Before claiming real source awareness:

- marketing has Telegram/MAX/YouTube/site exports or API access
- legal has the actual contract and organization-interest policy
- technical director has NotebookLM/RAG export or local technical documents
- production has the current production status file
- sales lead has Beeline exports, scripts and transcription path

Expected:

- agents name missing sources instead of inventing facts
- publication, legal, call export and external upload actions require approval

## Archive Privacy Gate

Search the built artifact for private traces:

```bash
rg -n -i "(/Users/|/home/|C:\\\\Users\\\\|api[_-]?key\\s*=\\s*[^[:space:]]+|token\\s*=\\s*[^[:space:]]+)" \
  runtime-template shared-generic project-vault-generic client-files README.md docs/README.md BUILD_MANIFEST.json
```

Expected:

- no real private tokens, chats, call recordings, contracts, or personal archives

## Release Verdict

The repo is ready to use when:

- fast gate passes
- full install gate passes
- department gate passes
- source gate is truthful
- archive privacy gate passes
