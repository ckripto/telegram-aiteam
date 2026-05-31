# Memory And Data Model

## Storage Goals

The system needs durable state for:

- Telegram messages;
- visible agent interaction;
- internal event log;
- agent runs;
- MCP tool calls;
- confirmations;
- memory;
- project records;
- task delegations;
- permission policies.

For local development, SQLite is enough. For production, use Postgres.

## Main Entities

### Workspace

Represents one organization or private environment.

Fields:

- `id`;
- `name`;
- `created_at`.

### Telegram Chat

Maps a Telegram group to a workspace.

Fields:

- `id`;
- `workspace_id`;
- `telegram_chat_id`;
- `title`;
- `created_at`;
- `is_active`.

### User

Maps Telegram users to internal users.

Fields:

- `id`;
- `workspace_id`;
- `telegram_user_id`;
- `display_name`;
- `role`;
- `created_at`.

### Agent

Stores virtual agent definitions.

Fields:

- `id`;
- `workspace_id`;
- `display_name`;
- `role`;
- `config`;
- `model_env`;
- `api_key_env`;
- `base_url_env`;
- `is_active`;
- `created_at`;
- `updated_at`.

### Event

Append-only event log.

Fields:

- `id`;
- `workspace_id`;
- `conversation_id`;
- `request_id`;
- `event_type`;
- `actor_type`;
- `actor_id`;
- `target_id`;
- `visibility`;
- `payload`;
- `telegram_message_id`;
- `created_at`.

Example event types:

- `telegram_message_received`;
- `agent_message`;
- `agent_delegation_requested`;
- `agent_delegation_accepted`;
- `agent_delegation_completed`;
- `tool_call_requested`;
- `tool_call_completed`;
- `confirmation_requested`;
- `confirmation_approved`;
- `confirmation_rejected`;
- `memory_written`;
- `error`.

### Agent Run

Represents one model invocation or one agent execution step.

Fields:

- `id`;
- `workspace_id`;
- `agent_id`;
- `request_id`;
- `status`;
- `input_event_ids`;
- `output_event_ids`;
- `model`;
- `started_at`;
- `completed_at`;
- `error`.

### Tool Call

Represents one MCP capability invocation.

Fields:

- `id`;
- `workspace_id`;
- `agent_id`;
- `capability`;
- `mcp_server`;
- `mcp_tool`;
- `arguments_redacted`;
- `status`;
- `result_summary`;
- `confirmation_id`;
- `started_at`;
- `completed_at`;
- `error`.

### Confirmation

Represents a user approval gate.

Fields:

- `id`;
- `workspace_id`;
- `request_id`;
- `agent_id`;
- `capability`;
- `action_summary`;
- `status`;
- `requested_by_event_id`;
- `approved_by_user_id`;
- `created_at`;
- `decided_at`.

Statuses:

- `pending`;
- `approved`;
- `rejected`;
- `expired`;

### Reminder

Represents a Telegram reminder created by the planner assistant.

Fields:

- `id`;
- `chat_id`;
- `user_id`;
- `text`;
- `due_at`;
- `status`;
- `created_at`;
- `sent_at`.

Statuses:

- `pending`;
- `sent`;
- future: `cancelled`;
- future: `expired`.

### Memory

Stores long-lived context.

Fields:

- `id`;
- `workspace_id`;
- `scope_type`;
- `scope_id`;
- `key`;
- `value`;
- `source_event_id`;
- `confidence`;
- `created_at`;
- `updated_at`.

Scope types:

- `workspace`;
- `user`;
- `project`;
- `agent`.

### Project

Represents a software development project.

Fields:

- `id`;
- `workspace_id`;
- `name`;
- `description`;
- `status`;
- `project_agent_id`;
- `created_at`;
- `updated_at`.

### Delegation

Represents a task assigned from one agent to another.

Fields:

- `id`;
- `workspace_id`;
- optional `project_id`;
- `request_id`;
- `from_agent_id`;
- `to_agent_id`;
- `task`;
- `status`;
- `created_event_id`;
- `result_event_id`;
- `created_at`;
- `completed_at`.

Statuses:

- `requested`;
- `accepted`;
- `in_progress`;
- `completed`;
- `rejected`;
- `cancelled`;

## Memory Rules

Agents should not silently store every message as long-term memory.

Recommended rules:

1. Store all raw activity in the event log.
2. Store long-term memory only when useful and justifiable.
3. Prefer explicit memory writes:

```text
[Assistant] I can remember that you prefer focus work after lunch. Should I save this?
```

4. Project decisions can be stored automatically when they are made in a project context.
5. Sensitive data should have expiration or manual deletion support.
