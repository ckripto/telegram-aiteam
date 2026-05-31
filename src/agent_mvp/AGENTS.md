# Runtime Package Agent Memory

## PURPOSE

`src/agent_mvp` implements the Telegram-visible multi-agent runtime: message polling, command routing, virtual agent definitions, model calls, tool gateways, persistence, reminders, and Telegram rendering. This is the primary place for product behavior changes.

## KEY FILES

- `__main__.py`: CLI entrypoint for `python3 -m src.agent_mvp`.
- `app.py`: composition root and long-polling loop; keeps compatibility wrapper methods for public app workflows.
- `routing.py`: Telegram message routing, explicit command handling, inbound event recording, and Assistant decision dispatch.
- `telegram_rendering.py`: visible Telegram message emission plus rendered event/delegation persistence.
- `specialist_workflows.py`: Weather, Planner/reminder, and Senior Python Developer workflows, including GitHub PR/file/merge commands.
- `agent_registry.py`: canonical registry of virtual agents, commands, capabilities, and per-agent model env vars.
- `assistant.py`: personal Assistant runtime, OpenAI Responses API call, prompt construction, and offline fallback behavior.
- `python_developer.py`: Senior Python Developer runtime plus repository planning and file-update JSON contracts.
- `github_gateway.py`: GitHub REST API gateway for repo resolution, file/tree reads, branch writes, draft PR creation, and confirmed PR merges.
- `telegram.py`: Telegram Bot API client, update parsing, and long-message splitting.
- `storage.py`: SQLite migrations, event/reminder persistence, and future memory/project schema foundation.
- `events.py`: event dataclass and id/time helpers.
- `config.py`: `.env` loading and runtime configuration properties.
- `reminders.py`: Russian/absolute reminder time parser.
- `weather.py`: Open-Meteo geocoding and forecast client.
- `mcp_stub.py`: placeholder MCP status surface for future MCP integration.

## RULES

- Keep all user-visible agent collaboration explicit through `emit_agent_message` and event records.
- Keep rendering behavior inside `telegram_rendering.py`; workflows should call the renderer instead of sending Telegram messages directly.
- Keep command routing in `routing.py`; specialist workflow execution belongs in `specialist_workflows.py`.
- Register new agents in `agent_registry.py`; Assistant must discover specialists from the registry instead of hidden hardcoded agents.
- Prefer explicit commands or structured model/router decisions over ad hoc natural-language substring routing.
- Model/tool credentials belong in `Config`; specialist agents may own separate model env vars.
- GitHub write operations must stay behind explicit user intent; merges require literal `CONFIRM`.
- Use complete replacement file content for GitHub file writes, matching current `python_developer.py` contracts.
- Keep Telegram output concise and rely on `TelegramClient.send_message` splitting for long messages.
- Add SQLite schema changes as new immutable `Migration` entries in `storage.py`; do not rewrite old migrations.
- Update neighboring `*.ast-summary.md` files whenever large Python module shape changes.

## GOTCHAS

- `GITHUB_DEFAULT_REPO` is the current project codebase; if it is a short name, `GitHubGateway` tries to resolve it through GitHub when unambiguous.
- Fine-grained GitHub tokens need repository `Contents: read/write` and `Pull requests: read/write` for the developer PR workflow.
- Telegram group privacy mode can prevent non-command messages from reaching the bot.
- `AssistantRuntime` has an offline fallback, but Senior Python Developer repository edits require `PYTHON_DEVELOPER_API_KEY` and `PYTHON_DEVELOPER_MODEL`.
- Free-form delayed requests should go to Planner first; when due, Assistant can re-delegate to Weather or another specialist.
- The MCP layer is a stub; do not assume real MCP tool access exists until a gateway is implemented.
