# Telegram Interaction Model

## Requirement

The Telegram group must show interaction between agents.

This means the group should contain visible operational messages:

- user requests;
- agent acknowledgements;
- agent-to-agent delegation;
- tool usage summaries;
- confirmation requests;
- progress updates;
- final results.

It should not expose private hidden reasoning. Agents must summarize their intent and actions in concise operational language.

## Message Format

Recommended format:

```text
[Assistant] I can help. I will check your calendar first.
[Assistant -> Calendar] Reading events for tomorrow.
[Assistant] Tomorrow is busy until 13:00. I suggest 14:00-15:30 for deep work.
```

For project work:

```text
[Project: Billing] I need a QA pass before release.
[Project: Billing -> QA] Please review payment retry scenarios.
[QA] Accepted. I will prepare a checklist.
[QA -> Project: Billing] Found 2 missing test cases.
```

## Routing Rule

Free-form user text must not be routed by substring checks or hardcoded keyword lists. Assistant is the default coordinator and should decide whether to delegate based on the registered agent list.

The backend may directly route:

- explicit commands;
- explicit mentions;
- pending confirmation ids;
- due scheduled intents from Planner.

Everything else should go through Assistant or a model-backed structured router.

## Event Visibility Levels

Each event should have a visibility level.

### `public`

Always posted to Telegram.

Examples:

- final answers;
- explicit agent messages;
- delegation requests;
- confirmation requests;
- completed task summaries.

### `compact`

Posted in summarized form.

Examples:

- tool calls;
- context retrieval;
- repeated progress updates;
- retries.

### `private`

Stored in the event log but not posted.

Examples:

- raw model payloads;
- sensitive tool results;
- internal scoring;
- permission checks;
- hidden reasoning.

## Agent Message Types

### User Request

```text
[User] Plan my day tomorrow.
```

### Agent Acknowledgement

```text
[Assistant] I will review your calendar and then suggest a plan.
```

### Tool Call Summary

```text
[Assistant -> Calendar] Reading events for 2026-06-01.
```

### Tool Result Summary

```text
[Calendar -> Assistant] Found 5 events, 2 free blocks.
```

### Weather Agent

```text
[Assistant] Вижу запрос про погоду. Делегирую его агенту Weather.
[Assistant -> Weather] Получи прогноз на сегодня для: Moscow.
[Weather] Принял. Проверю прогноз для: Moscow.
[Weather -> Assistant] Moscow: Сейчас 18°C, ветер 9 км/ч. Сегодня ожидается от 12°C до 20°C.
[Assistant] По данным Weather: Moscow: Сейчас 18°C, ветер 9 км/ч. Сегодня ожидается от 12°C до 20°C.
```

Assistant must not simulate this sequence with plain model text. If a specialist is needed, the router/orchestrator must invoke the specialist runtime and render the specialist response in the chat.

### Senior Python Developer

```text
[Assistant] Делегирую задачу агенту Senior Python Developer.
[Assistant -> Senior Python Developer] Спроектируй FastAPI endpoint для задач.
[Senior Python Developer] Принял задачу. Подготовлю технический ответ.
[Senior Python Developer -> Assistant] Рекомендую ...
[Assistant] Senior Python Developer вернул результат:
Рекомендую ...
```

Specialist agents may use their own model credentials. The Telegram protocol does not expose tokens, but the registry and runtime should make it clear which agent owns which model configuration.

### GitHub PR

```text
[User] /python_pr feature main Add GitHub skill
[Assistant] Делегирую Senior Python Developer подготовку PR description.
[Senior Python Developer -> Assistant] Подготовил PR body:
...
[Assistant -> GitHub] Открываю draft PR в ckripto/telegram-aiteam: feature -> main.
[GitHub -> Assistant] Pull request created: https://github.com/ckripto/telegram-aiteam/pull/1
[Assistant] PR открыт: https://github.com/ckripto/telegram-aiteam/pull/1
```

Opening a PR is a write action. Explicit `/python_pr` commands can execute immediately; autonomous PR creation should request confirmation first. If the command omits `repo`, GitHub uses `GITHUB_DEFAULT_REPO` as the current project codebase.

### Developer Task To PR

```text
[User] /python_dev Добавить фитчу: сообщения в Telegram должны быть размечены в markdown. Открыть PR в репозиторий.
[Assistant -> Senior Python Developer] Default GitHub repository/current project: telegram-aiteam.
[Senior Python Developer -> GitHub] Запрашиваю репозиторий по умолчанию: telegram-aiteam.
[GitHub -> Senior Python Developer] Текущий проект: ckripto/telegram-aiteam, base branch: main.
[Senior Python Developer -> GitHub] Для PR прочитаю файлы:
- src/agent_mvp/telegram.py
- src/agent_mvp/app.py
[Senior Python Developer -> Assistant] Подготовил изменения для ветки codex/telegram-markdown.
[GitHub -> Assistant] Pull request created: https://github.com/ckripto/telegram-aiteam/pull/13
[Assistant] Senior Python Developer открыл draft PR: https://github.com/ckripto/telegram-aiteam/pull/13
```

This flow is for explicit PR requests in developer tasks. The visible Telegram conversation must show Assistant, Senior Python Developer, and GitHub steps so the user can audit what happened.

### GitHub Code Change

```text
[User] /python_change_file main codex/readme-update README.md Add setup instructions
[Assistant -> Senior Python Developer] Прочитай файл README.md из ckripto/telegram-aiteam@main.
[GitHub -> Senior Python Developer] Read README.md from ckripto/telegram-aiteam@main.
[Assistant] Делегирую Senior Python Developer изменение README.md через PR.
[Senior Python Developer -> Assistant] Изменил README.md в ветке codex/readme-update.
[Assistant] PR с изменением открыт: https://github.com/ckripto/telegram-aiteam/pull/12
```

`GITHUB_DEFAULT_REPO` is the repository for the current software project and for the agent workspace itself. Senior Python Developer should use it whenever the user says "this project", "current code", or omits a repository in GitHub commands.

### GitHub Merge

```text
[User] /python_merge_pr 12 CONFIRM
[Assistant -> GitHub] Получено прямое указание. Мержу PR #12 в ckripto/telegram-aiteam.
[GitHub -> Assistant] PR #12 смержен. SHA: ...
```

Merging requires the explicit command and literal `CONFIRM`. The assistant must not merge a PR from an indirect or ambiguous natural-language instruction.

### Long Messages

Telegram rejects messages over its length limit. The Telegram client splits outgoing text into safe chunks before calling `sendMessage`; the first chunk may reply to the original message, and following chunks are sent as continuation messages.

### Planner Reminder

```text
[Planner] Готово, напомню.
ID: rem_123
Когда: через 10 мин.
Что: проверить сборку
```

When the reminder is due:

```text
[Planner] Напоминание: проверить сборку
```

### Deferred Intent

```text
[User] проверь погоду в питере через час
[Assistant] Это отложенная задача. Делегирую Planner, чтобы вернуться к ней через час.
[Assistant -> Planner] Через час верни мне задачу: проверить текущую погоду в Питере.
[Planner -> Assistant] Принял. Верну задачу через час.
```

One hour later:

```text
[Planner -> Assistant] Пора выполнить отложенную задачу: проверить текущую погоду в Питере.
[Assistant] Для этой задачи нужен Weather.
[Assistant -> Weather] Получи текущую погоду для: Saint Petersburg.
[Weather -> Assistant] Saint Petersburg: Сейчас 18°C...
[Assistant] Напоминаю, вы просили проверить погоду. По данным Weather: Saint Petersburg: Сейчас 18°C...
```

### Delegation

```text
[Project: Mobile App -> Designer] Please review the onboarding flow.
```

### Acceptance

```text
[Designer] Accepted. I will review the flow and report back here.
```

### Progress

```text
[Backend Dev] I inspected the API contract. Checking edge cases now.
```

### Completion

```text
[Backend Dev -> Project: Mobile App] Completed. Main risk: auth refresh handling.
```

### Confirmation Request

```text
[Assistant] I can create this calendar event:
Title: Focus work
Time: 2026-06-01 14:00-15:30

Reply: /confirm act_123 or /cancel act_123
```

### Confirmation Result

```text
[Assistant -> Calendar] Creating event after user confirmation.
[Assistant] Done. The event was added to your calendar.
```

## Avoiding Chat Noise

The system should show collaboration, but avoid flooding the group.

Use these rules:

1. Show all delegations and completion reports.
2. Show tool calls in compact form.
3. Group repeated progress updates.
4. Suppress low-value internal events.
5. Use message edits for long-running status when appropriate.
6. Apply per-agent rate limits.

## Commands

Initial commands:

- `/agents` - list active agents in this group.
- `/agent_status` - show agent availability and current tasks.
- `/confirm <action_id>` - approve a pending action.
- `/cancel <action_id>` - reject a pending action.
- `/weather <city>` - ask the weather assistant for a forecast.
- `/remind <time> <text>` - create a Telegram reminder.
- `/reminders` - list pending reminders.
- `/memory` - show memory controls.
- `/projects` - list projects visible in this group.

Future commands:

- `/assign <project> <agent>` - assign an agent to a project.
- `/delegate <agent> <task>` - manually delegate a task.
- `/mute_agent <agent>` - reduce visibility.
- `/unmute_agent <agent>` - restore visibility.

## Threading Model

Telegram groups do not provide perfect structured threading for bot messages. The backend should maintain its own correlation ids.

Every request should have:

- `request_id`;
- `conversation_id`;
- `workspace_id`;
- optional `project_id`;
- optional `parent_event_id`;
- optional `delegation_id`.

When possible, the bot can reply to specific Telegram messages, but internal correlation must not rely only on Telegram reply chains.
