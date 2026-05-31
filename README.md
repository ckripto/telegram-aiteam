# Telegram Multi-Agent Workspace

Telegram-visible workspace for coordinating virtual agents.

Current scope:

- one real Telegram bot;
- four example virtual agents: `personal_assistant`, `weather_assistant`, `planner_assistant`, `senior_python_developer`;
- visible interaction messages in the Telegram group;
- local SQLite event log;
- OpenAI-compatible assistant runtime through the Responses API;
- offline fallback runtime when OpenAI credentials are not configured;
- per-agent model credentials for specialist agents;
- example weather capability through Open-Meteo;
- persisted Telegram reminders;
- extension points for MCP tools, CrewAI, and future project agents.

Architecture notes live in [docs](./docs).

## Quick Start

Before running the bot in a group, make sure it can receive the messages you expect:

- if you want the assistant to see every group message, disable bot privacy mode in BotFather;
- if privacy mode stays enabled, Telegram will usually deliver only commands, replies, and mentions.

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Fill in:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHAT_ID=...
OPENAI_API_KEY=...
OPENAI_MODEL=...
PYTHON_DEVELOPER_API_KEY=...
PYTHON_DEVELOPER_MODEL=...
PYTHON_DEVELOPER_BASE_URL=https://api.openai.com/v1
GITHUB_TOKEN=...
GITHUB_DEFAULT_REPO=ckripto/telegram-aiteam
GITHUB_API_BASE_URL=https://api.github.com
LOCAL_TIMEZONE=Europe/Moscow
WEATHER_DEFAULT_LOCATION=Moscow
```

`TELEGRAM_ALLOWED_CHAT_ID` is optional for local testing, but recommended. If set, the bot ignores messages from other chats.

3. Run the bot with long polling:

```bash
python3 -m src.agent_mvp
```

## Telegram Commands

- `/help` - show available commands.
- `/agents` - list active virtual agents.
- `/status` - show runtime and storage status.
- `/weather <city>` - ask the weather assistant for today's forecast.
- `/remind <time> <text>` - ask the planner to remind you in Telegram.
- `/reminders` - list pending reminders for the group.
- `/python_dev <task>` - delegate to Senior Python Developer.
- `/python_pr [repo] <head> <base> <title>` - ask Senior Python Developer to prepare a PR body and open a draft GitHub PR.
- `/python_file [repo] <ref> <path>` - ask Senior Python Developer to read a file from GitHub.
- `/python_change_file [repo] <base> <branch> <path> <task>` - ask Senior Python Developer to edit a file on a branch and open a draft PR.
- `/python_merge_pr [repo] <number> CONFIRM` - merge a PR only after explicit confirmation.
- `/prompt_for_agent <role>: <task>` - ask the assistant to prepare a prompt for a future agent.

Reminder examples:

```text
/remind через 10 минут проверить сборку
/remind сегодня 18:30 созвониться с командой
/remind завтра 09:30 написать план дня
/remind 2026-06-01 09:30 созвон
```

## How The Workspace Behaves

For a normal group message, the bot posts visible operational messages:

```text
[Assistant] Принял запрос. Разберу его как личный помощник.
[Assistant] ...
```

For clear specialist requests, Assistant delegates visibly and then returns the final answer:

```text
[Assistant] Вижу запрос про погоду. Делегирую его агенту Weather.
[Assistant -> Weather] Получи прогноз на сегодня для: Saint Petersburg.
[Weather -> Assistant] Saint Petersburg: Сейчас ...
[Assistant] По данным Weather: Saint Petersburg: Сейчас ...
```

If Assistant only says that it will contact another agent, but no `[Assistant -> Agent]` and `[Agent -> Assistant]` messages follow, that is a routing/orchestration bug. Specialist work should be real and visible.

Target routing model: Assistant decides free-form delegation from the registered agent list. Do not add keyword checks like `"погод" in text` for natural-language routing; use explicit commands or structured Assistant/model decisions instead.

Deferred intent example:

```text
User: проверь погоду в питере через час
Assistant -> Planner: Верни эту задачу через час.
Planner -> Assistant, one hour later: Пора проверить погоду в Питере.
Assistant -> Weather: Получи текущую погоду для Saint Petersburg.
Weather -> Assistant: ...
Assistant -> User: Напоминаю, вы просили проверить погоду. Сейчас ...
```

If `OPENAI_API_KEY` and `OPENAI_MODEL` are set, the assistant calls the OpenAI API.

If they are not set, the assistant uses a deterministic offline fallback. This keeps Telegram integration testable before model credentials are ready.

Specialist agents may use their own model credentials. For example, Senior Python Developer reads:

```text
PYTHON_DEVELOPER_API_KEY
PYTHON_DEVELOPER_MODEL
PYTHON_DEVELOPER_BASE_URL
```

Senior Python Developer can also use GitHub capabilities when `GITHUB_TOKEN` is configured:

```text
/python_pr feature-branch main Add GitHub skill
/python_file main README.md
/python_change_file main codex/readme-update README.md Add setup instructions
/python_merge_pr 12 CONFIRM
```

When `repo` is omitted, the GitHub gateway uses `GITHUB_DEFAULT_REPO`. Treat this value as the current project repository: it is the codebase being developed, including the Telegram AI team itself. Commands may still pass an explicit `owner/repo` to work with another repository.

`/python_change_file` creates or reuses the requested branch, writes the generated full-file replacement there, and opens a draft PR. `/python_merge_pr` is intentionally strict and requires the literal `CONFIRM`.

## Project Structure

```text
src/agent_mvp/
  __main__.py          CLI entrypoint
  agent_registry.py    Virtual agent definitions
  app.py              Main polling application
  assistant.py        Assistant runtime and prompts
  config.py           Environment loading
  events.py           Event model
  mcp_stub.py         Placeholder MCP capability layer
  python_developer.py Senior Python Developer runtime
  reminders.py        Reminder parsing
  storage.py          SQLite event log
  telegram.py         Telegram Bot API client
  weather.py          Open-Meteo weather capability
```

When adding new agents, start with [docs/adding-agents.md](./docs/adding-agents.md). It is the short maintenance guide intended to avoid rereading the whole repository.

## Next Development Steps

1. Add webhook mode for production deployment.
2. Add real MCP gateway and capability registry.
3. Add confirmation flow for write actions.
4. Add project agents and delegation events.
5. Add CrewAI or another multi-agent runtime behind the existing agent runtime interface.

## CrewAI Integration Point

CrewAI should be introduced behind the assistant runtime boundary, not inside the Telegram adapter.

The replacement path is:

```text
src/agent_mvp/assistant.py
  AssistantRuntime.respond(...)
```

Telegram, event storage, command handling, MCP permissions, and visible rendering should stay outside CrewAI. That keeps the user-visible group protocol stable even if the agent runtime changes.
