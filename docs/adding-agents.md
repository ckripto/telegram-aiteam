# Adding New Agents

This is the short guide for extending the workspace without rereading the whole repository.

## Current Runtime Shape

The bot has one Telegram adapter and multiple virtual agents.

```text
Telegram update
  -> AgentWorkspaceApp.handle_message
  -> Assistant as default coordinator
  -> optional visible delegation to a specialist agent
  -> specialist runtime/tool
  -> result returned to Assistant
  -> EventStore
  -> Assistant final message in Telegram
```

The important files are:

- `src/agent_mvp/agent_registry.py` - declare the agent, commands, and capabilities.
- `src/agent_mvp/app.py` - route commands/messages to the agent.
- `src/agent_mvp/storage.py` - add persistence only when the agent needs durable state.
- `src/agent_mvp/mcp_stub.py` - list demo capabilities until the real MCP gateway exists.
- `tests/` - add small tests around parsing, routing helpers, and storage.

## Add An Agent Checklist

1. Add an `AGENT_ID` constant and `AgentDefinition` in `agent_registry.py`.
2. Give the agent a display name that works in Telegram, for example `[QA]` or `[Weather]`.
3. Add capabilities using stable names such as `qa.prepare_checklist` or `weather.forecast`.
4. Set `receives_delegations=True` when Assistant may assign work to this agent.
5. Add the specialist to `format_assistant_agent_context()` by keeping it in the shared `AGENTS` registry.
6. If the agent uses a dedicated model, set `model_env`, `api_key_env`, and optional `base_url_env`.
7. Add explicit command routing in `handle_command` when the command is part of the product.
8. Do not add keyword-based natural-language routing in `handle_message`.
9. Expose the agent through the registry so Assistant/model routing can choose it.
10. Route user-facing specialist work through Assistant delegation, not as an invisible direct call.
11. Emit all visible messages through `emit_agent_message(..., agent_id=...)`.
12. Store delegation with `agent_delegation_requested` and meaningful internal events with `EventStore.append`.
13. Return specialist results to Assistant, then let Assistant publish the final user-facing summary.
14. Add tests for parsing and deterministic behavior.
15. Update this guide if the new agent introduces a new pattern.

## Assistant Must Know Every Agent

Every agent must be registered in `src/agent_mvp/agent_registry.py`.

Do not create agents only inside `app.py` or a one-off module. The registry is the single source of truth used for:

- `/agents` output;
- Assistant's available-agent context;
- delegation policy;
- per-agent model configuration;
- future CrewAI or MCP agent initialization.

For now, `format_assistant_agent_context()` builds the specialist list injected into the Assistant runtime. When more advanced routing arrives, it should still read from the same registry.

## No Keyword Routing

Do not route free-form user text with substring checks such as:

```text
if "погод" in text: route_to_weather()
```

That approach will not scale to multi-step requests and creates hidden behavior that Assistant cannot reason about.

Free-form routing should work like this:

1. Telegram adapter receives the message.
2. Assistant receives the user request plus the registered agent list.
3. Assistant returns a structured plan or delegation decision.
4. Orchestrator executes that decision and renders every agent-to-agent message.

Explicit commands are still allowed because they are direct product controls:

```text
/weather Moscow
/remind через 10 минут проверить сборку
```

Natural language should be decided by Assistant/model routing, not by string matching.

## Per-Agent Models

Agents may use different models and different API tokens.

Use the registry to document which environment variables configure the agent:

```python
AgentDefinition(
    id=SENIOR_PYTHON_DEVELOPER_ID,
    display_name="Senior Python Developer",
    ...
    model_env="PYTHON_DEVELOPER_MODEL",
    api_key_env="PYTHON_DEVELOPER_API_KEY",
    base_url_env="PYTHON_DEVELOPER_BASE_URL",
)
```

Runtime rules:

1. Assistant gets the full agent list and can delegate to specialists.
2. The specialist runtime reads only its own model credentials.
3. Missing specialist credentials should not break the workspace; the specialist should return a visible configuration message.
4. Do not reuse Assistant's model token implicitly for a specialist that is documented as having its own model.

## Delegation Pattern

Specialist requests should flow through Assistant:

```text
[Assistant] Вижу запрос про погоду. Делегирую его агенту Weather.
[Assistant -> Weather] Получи прогноз на сегодня для: Saint Petersburg.
[Weather] Принял. Проверю прогноз для: Saint Petersburg.
[Weather -> Assistant] Saint Petersburg: Сейчас ...
[Assistant] По данным Weather: Saint Petersburg: Сейчас ...
```

This must be a real runtime call, not a model-generated promise. Assistant must not send text like "I am contacting Weather" unless the application then actually calls the specialist agent and posts the specialist response.

Required visible sequence:

1. Assistant announces delegation.
2. Assistant sends a visible request to the specialist.
3. Specialist acknowledges or executes.
4. Specialist returns a visible result to Assistant.
5. Assistant posts the final answer to the user.

The same rule applies to future agents:

```text
[Assistant -> QA] Проверь сценарии оплаты для релиза.
[QA -> Assistant] Нашёл 2 недостающих сценария.
[Assistant] QA вернул результат: ...
```

Direct specialist commands like `/weather Moscow` may exist for debugging and explicit control, but they should still use the same delegation protocol where possible.

## Deferred Intent Pattern

Planner should store deferred user intent, not only final reminder text.

Example request:

```text
User: проверь погоду в питере через час
```

Expected flow:

```text
[Assistant] Понял: нужно выполнить задачу позже. Делегирую отложенное выполнение Planner.
[Assistant -> Planner] Через час верни мне задачу: проверить текущую погоду в Питере.
[Planner -> Assistant] Принял. Верну задачу через час.
```

One hour later:

```text
[Planner -> Assistant] Пора выполнить отложенную задачу: проверить текущую погоду в Питере.
[Assistant] Для этой задачи нужен Weather.
[Assistant -> Weather] Получи текущую погоду для: Saint Petersburg.
[Weather -> Assistant] Saint Petersburg: Сейчас ...
[Assistant] Напоминаю: вы просили проверить погоду через час. По данным Weather: ...
```

Planner does not decide the final specialist chain unless explicitly designed for that. Its core responsibility is delayed delivery of intent back to Assistant. Assistant remains the coordinator and decides the next delegation step at execution time.

## Message Visibility Rule

Telegram should show operational collaboration, not hidden reasoning.

Good:

```text
[Assistant -> Weather] Получи прогноз на сегодня для: Moscow.
[Weather -> Assistant] Moscow: Сейчас 18°C...
[Assistant] По данным Weather: Moscow: Сейчас 18°C...
```

Good:

```text
[Planner] Готово, напомню.
ID: rem_123
Когда: через 10 мин.
Что: проверить сборку
```

Avoid:

```text
Raw internal model reasoning, raw API responses, secrets, full private documents.
```

## Tool And Capability Pattern

Use capability names in agent definitions and events.

Examples:

- `weather.forecast`;
- `reminder.create`;
- `reminder.list`;
- `agent_prompt.prepare`;
- `telegram.send_message`.

Today `mcp_stub.py` only documents demo capabilities. Later it should be replaced by the real MCP gateway described in [mcp-permissions.md](./mcp-permissions.md).

## Persistence Pattern

Use the append-only `events` table for traceability.

Create a dedicated table only when the agent has durable operational state:

- reminders need a `reminders` table;
- project agents will likely need `projects`, `delegations`, and task mapping tables;
- weather does not need a table because forecasts are transient and tool calls are already logged as events.

## Command Pattern

Commands are stable explicit controls:

```text
/weather Moscow
/remind через 10 минут проверить сборку
```

Free-form natural language must still go through Assistant/model routing. Example:

```text
User: Подскажи мне погоду на сегодня в Питере
Assistant decides: delegate to Weather
Assistant -> Weather
Weather -> Assistant
Assistant -> User
```

## Testing Pattern

Prefer tests that do not call external services.

Good tests:

- reminder text parsing;
- event storage;
- agent prompt fallback;
- routing helper functions;
- weather response formatting with mocked data when mocks are introduced.

Avoid tests that require:

- Telegram network access;
- OpenAI API credentials;
- live weather API calls.

## Current Example Agents

### `personal_assistant`

Files:

- `assistant.py`;
- route in `app.py`;
- command `/prompt_for_agent`.

Purpose:

- answer general questions;
- prepare prompts for future agents;
- act as the default route.

### `weather_assistant`

Files:

- `weather.py`;
- route in `app.py`;
- command `/weather`.

Purpose:

- fetch weather through Open-Meteo;
- publish compact visible tool activity.
- return the forecast to Assistant for the final user-facing answer.

### `planner_assistant`

Files:

- `reminders.py`;
- reminder persistence in `storage.py`;
- scheduler in `app.py`;
- commands `/remind` and `/reminders`.

Purpose:

- create durable Telegram reminders;
- send reminders back to the same group.

### `senior_python_developer`

Files:

- `python_developer.py`;
- route in `app.py`;
- command `/python_dev`.

Purpose:

- review and design Python code;
- debug Python/backend problems;
- use its own model credentials through `PYTHON_DEVELOPER_API_KEY`, `PYTHON_DEVELOPER_MODEL`, and `PYTHON_DEVELOPER_BASE_URL`.
