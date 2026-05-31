# Source Tree Agent Memory

## PURPOSE

`src` contains the importable application package. Keep runtime code under `src/agent_mvp` and avoid placing executable logic directly in this directory.

## KEY FILES

- `agent_mvp/`: main Python package for Telegram orchestration, agent runtimes, tools, and persistence.

## RULES

- Imports should use package-relative imports inside `src/agent_mvp`.
- Keep CLI entrypoints inside package modules so `python3 -m src.agent_mvp` remains the canonical run command.
- Do not add generated caches or local runtime state under `src`.

## GOTCHAS

- The public package path is still `src.agent_mvp` for compatibility, even though product language no longer calls the project an MVP.
- Tests import modules through `src.agent_mvp`, so package moves require test and command updates.
