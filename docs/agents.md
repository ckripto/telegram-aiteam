# Agents And Roles

## Agent Definition

Each virtual agent should be defined with:

- `id`;
- `display_name`;
- `description`;
- `role_prompt`;
- `default_visibility`;
- `allowed_tools`;
- `memory_scopes`;
- `can_delegate_to`;
- `can_receive_delegations`;
- `requires_confirmation_for`;
- `max_parallel_tasks`;
- optional `model_env`;
- optional `api_key_env`;
- optional `base_url_env`;

Example:

```yaml
id: personal_assistant
display_name: Assistant
description: Personal assistant for scheduling, questions, and coordination.
default_visibility: public
allowed_tools:
  - calendar.read
  - calendar.create_event
  - tasks.read
  - tasks.create
  - docs.search
memory_scopes:
  - user
  - workspace
can_delegate_to: []
can_receive_delegations: true
requires_confirmation_for:
  - calendar.create_event
  - tasks.create
max_parallel_tasks: 3
```

Agents may use the shared Assistant model or their own model credentials. When an agent has dedicated model settings, document the environment variables in its registry entry and runtime docs.

## Initial Agent: Personal Assistant

Responsibilities:

- answer user questions;
- plan schedule;
- ask clarifying questions;
- read calendar and task data through MCP;
- propose calendar/task changes;
- request confirmation before mutations;
- remember user preferences when explicitly allowed;
- summarize decisions in Telegram.

Default behavior:

1. Acknowledge the request in Telegram.
2. Check the registered agent list for a better specialist owner.
3. Delegate specialist work visibly when appropriate.
4. Receive specialist results.
5. Use allowed MCP tools directly only for Assistant-owned capabilities.
6. Ask for confirmation before changing anything.
7. Report the final result to the user.

Assistant must know every available agent through `src/agent_mvp/agent_registry.py`. New agents should not be hidden in one-off code paths, because Assistant uses the registry as its delegation map.

Assistant must not fake delegation. For specialist-owned requests, the application must call the specialist agent and show the actual agent-to-agent messages in Telegram before Assistant gives the final answer.

Assistant, not keyword routing code, owns free-form delegation decisions. The backend may route explicit commands and pending action ids directly, but ordinary text should be interpreted by Assistant or by a model-backed structured router using the same agent registry.

Current command:

```text
/prompt_for_agent <role>: <task>
```

## Current Example Agent: Weather Assistant

Responsibilities:

- receive weather requests from Telegram;
- call a weather capability through the tool layer;
- publish concise forecast summaries;
- return weather results to Assistant when delegated;
- avoid storing forecasts as long-term memory.

Current command:

```text
/weather <city>
```

Current capability:

```text
weather.forecast
```

## Current Example Agent: Planner Assistant

Responsibilities:

- parse reminder requests;
- persist reminders;
- send Telegram reminders when they become due;
- list pending reminders for the group.
- return scheduling results to Assistant when delegated.
- store deferred user intent and return it to Assistant when due.
- avoid deciding a full future specialist chain unless explicitly instructed.

Deferred intent example:

```text
User: проверь погоду в питере через час
Assistant -> Planner: Через час верни мне задачу "проверить текущую погоду в Питере".
Planner -> Assistant, one hour later: Пора выполнить отложенную задачу.
Assistant -> Weather: Получи текущую погоду для Saint Petersburg.
Weather -> Assistant: ...
Assistant -> User: Напоминаю, вы просили проверить погоду. Сейчас ...
```

Current commands:

```text
/remind <time> <text>
/reminders
```

Current capabilities:

```text
reminder.create
reminder.list
telegram.send_message
```

## Current Example Agent: Senior Python Developer

Responsibilities:

- review Python code and architecture;
- design Python backend components;
- debug Python issues;
- explain Python tradeoffs;
- return technical output to Assistant for the final user-facing summary.

Current command:

```text
/python_dev <task>
```

Current capabilities:

```text
python.code_review
python.design
python.debug
python.explain
```

Dedicated model configuration:

```text
PYTHON_DEVELOPER_API_KEY
PYTHON_DEVELOPER_MODEL
PYTHON_DEVELOPER_BASE_URL
```

## Future Agent: Project Agent

One project agent should exist per software project.

Responsibilities:

- understand project goals and constraints;
- maintain project context;
- coordinate specialist agents;
- track backlog and decisions;
- ask the user for priority decisions;
- publish project status in Telegram.

Example id:

```text
project_billing
```

Example display name:

```text
Project: Billing
```

## Future Specialist Agents

### Backend Developer

Responsibilities:

- inspect backend requirements;
- propose implementation plans;
- write backend tasks;
- review API risks;
- coordinate with QA.

### Frontend Developer

Responsibilities:

- inspect UI requirements;
- propose frontend implementation plans;
- coordinate with design;
- identify state and API needs.

### Designer

Responsibilities:

- clarify UX requirements;
- propose user flows;
- review interface consistency;
- prepare design tasks.

### QA

Responsibilities:

- define test scenarios;
- review acceptance criteria;
- identify missing edge cases;
- create test plans.

### Release Manager

Responsibilities:

- coordinate release checklist;
- inspect CI/deployment status through MCP;
- prepare release notes;
- request confirmation before deployment.

## Delegation Rules

Delegation must be explicit and visible.

Example:

```text
[Project: Billing -> QA] Please prepare test scenarios for failed card retries.
```

Workspace example:

```text
[Assistant] Вижу запрос про погоду. Делегирую его агенту Weather.
[Assistant -> Weather] Получи прогноз на сегодня для: Saint Petersburg.
[Weather -> Assistant] Saint Petersburg: Сейчас 12°C...
[Assistant] По данным Weather: Saint Petersburg: Сейчас 12°C...
```

Delegation records should include:

- `delegation_id`;
- `from_agent_id`;
- `to_agent_id`;
- `task`;
- `context_refs`;
- `status`;
- `created_at`;
- `deadline`;
- `result_event_id`.

## Preventing Runaway Agent Loops

Use these constraints:

- max delegation depth per user request;
- max agents activated per request;
- max tool calls per agent turn;
- max public messages per minute;
- explicit permission for project agents to delegate;
- event log detection for repeated loops.
