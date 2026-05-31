# Repository Agent Memory

## PROJECT GOAL

Telegram Multi-Agent Workspace is a Python Telegram bot that makes virtual agent collaboration visible in a group chat. The current implementation has a personal Assistant, Weather, Planner, and Senior Python Developer agents, with SQLite event persistence, OpenAI-compatible model runtimes, weather/reminder capabilities, and a GitHub workflow that can read code, write branches, open draft PRs, and merge only after explicit confirmation.

## ARCHITECTURE DIAGRAM

```text
Telegram Group
    |
Telegram Bot API long polling
    |
TelegramClient / parse_message
    |
AgentWorkspaceApp
    |-- command router
    |-- visible event renderer
    |-- reminder scheduler
    |
    +--> AssistantRuntime
    |       |-- OpenAI Responses API
    |       `-- offline fallback
    |
    +--> Specialist agents
    |       |-- WeatherService -> Open-Meteo
    |       |-- Planner -> ReminderParser/EventStore
    |       `-- SeniorPythonDeveloperRuntime
    |              `-- own OpenAI-compatible model
    |
    +--> GitHubGateway -> GitHub REST API
    |
    +--> McpGatewayStub -> future MCP servers
    |
    `--> EventStore -> SQLite
```

## AGENT ROLES

- `personal_assistant`: user-facing coordinator, answers general questions, delegates specialist work, prepares prompts for future agents.
- `weather_assistant`: returns weather forecasts through the public weather provider.
- `planner_assistant`: creates, lists, stores, and delivers Telegram reminders.
- `senior_python_developer`: handles Python/backend design, code review, GitHub file reads, branch writes, draft PR creation, and confirmed PR merges through its own model credentials.
- TODO `project_agent`: one coordinator per software project, responsible for project memory, task breakdown, and delegation to specialists.
- TODO `design_agent`: product/UI design specialist.
- TODO `qa_agent`: test planning and quality specialist.
- TODO `devops_agent`: deployment, CI, runtime, and observability specialist.

## QUICK COMMANDS

- Run bot: `python3 -m src.agent_mvp`
- Run tests: `python3 -m unittest discover -s tests`
- Compile check: `python3 -m compileall src tests`
- Lint: not configured; use `git diff --check` for whitespace until a linter is added.
- Build: not configured; this is a source-run Python project.
- Manifests: no `package.json`, `requirements.txt`, or `pyproject.toml` is currently present.

## MEMORY RULES

- Read the nearest `AGENTS.md` before editing a directory.
- For Python files with a neighboring `*.ast-summary.md`, read the summary first and open the full source only when implementation details are needed.
- Do not reread a large file when an up-to-date AST summary already answers the question.

## TECH STACK

- Python 3 standard library application.
- Telegram Bot API through `urllib.request`.
- OpenAI-compatible Responses API for Assistant and specialist model runtimes.
- SQLite for local durable event/reminder storage.
- GitHub REST API for repository reads, branch writes, PR creation, and PR merges.
- Open-Meteo public API for weather.
- `unittest` test suite.

## CHANGE LOG

- 2026-05-31, Documentation Agent: created repository context bootstrap with root and directory `AGENTS.md` files plus AST summaries for large Python files.
