# Developer Workflow

This project is a source-run Python application with no packaging manifest yet. Use the commands below as the canonical local workflow until a `pyproject.toml` or task runner is added.

## Commands

- Run bot: `python3 -m src.agent_mvp`
- Run tests: `python3 -m unittest discover -s tests`
- Compile check: `python3 -m compileall src tests`
- Whitespace check: `git diff --check`
- Build: not configured.
- Lint: not configured.

## Environment Template

Copy the committed template before local runs:

```bash
cp .env.example .env
```

`TELEGRAM_BOT_TOKEN` is required to run the real bot. Model, GitHub, weather, and chat-scope settings are optional or have defaults documented in `.env.example` and `README.md`.

When adding or renaming environment variables:

1. Update `.env.example`.
2. Update `README.md` if users need the variable to run the bot.
3. Update `src/agent_mvp/AGENTS.md` if the variable changes an agent/runtime responsibility.
4. Add or adjust tests that instantiate `Config` directly.

## Repository Memory

Before editing any directory, read the nearest `AGENTS.md`. If a Python file has a neighboring `*.ast-summary.md`, read that summary first and open the source only when details are needed.

Update repository memory when the architecture changes:

- Root `AGENTS.md`: project-wide goals, commands, tech stack, cross-cutting rules.
- Directory `AGENTS.md`: local module ownership, gotchas, runtime boundaries.
- `*.ast-summary.md`: public classes/functions and material shape changes for large Python files.

If a refactor moves responsibilities between modules, update both `docs/modules.md` and the relevant `AGENTS.md` in the same change.

## SQLite Schema Changes

SQLite schema changes live in `src/agent_mvp/storage.py` as versioned stdlib migrations. To add a migration:

1. Append a new `Migration` to `MIGRATIONS`.
2. Keep existing migrations immutable.
3. Use idempotent SQL where practical.
4. Add tests for a new database and for repeated initialization.
5. Update `docs/memory-data.md` and `src/agent_mvp/storage.py.ast-summary.md`.

Existing `events` and `reminders` tables are runtime-critical. Do not rewrite or drop them in a migration unless a backward-compatible data migration and tests are included.

## PR Checklist

Before handing off a change:

1. Run `python3 -m unittest discover -s tests`.
2. Run `python3 -m compileall src tests`.
3. Run `git diff --check`.
4. Confirm public Telegram commands and visible message text were not changed unless the task explicitly asks for it.
5. Confirm docs navigation still points future agents to the right files.
