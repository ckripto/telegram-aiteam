# MCP And Permissions

## Purpose

MCP servers provide access to internal systems. The backend should never expose every MCP tool to every agent. Tools must be mapped into capabilities and granted by policy.

## MCP Gateway

The MCP Gateway is the only module allowed to invoke MCP tools.

Responsibilities:

- connect to MCP servers;
- discover tools and resources;
- map raw tool names to stable internal capability names;
- apply timeouts;
- normalize results;
- record all requests and responses;
- redact sensitive data before public rendering.

## Capability Naming

Use stable capability names instead of raw MCP tool names in agent configs.

Examples:

```text
calendar.read
calendar.create_event
calendar.update_event
tasks.read
tasks.create
docs.search
repo.search
repo.read
ci.read
deployment.trigger
weather.forecast
reminder.create
reminder.list
telegram.send_message
python.code_review
python.design
python.debug
python.explain
```

## Tool Classification

Every capability should be classified.

### Read

Does not mutate external state.

Examples:

- `calendar.read`;
- `tasks.read`;
- `docs.search`;
- `repo.read`;
- `weather.forecast`;
- `reminder.list`.
- `python.code_review`;
- `python.design`;
- `python.debug`;
- `python.explain`.

### Write

Creates or changes external state.

Examples:

- `calendar.create_event`;
- `tasks.create`;
- `tasks.update`;
- `repo.create_issue`;
- `reminder.create`;
- `telegram.send_message`.

### Dangerous

Can cause production impact, send external communication, delete data, or spend money.

Examples:

- `deployment.trigger`;
- `billing.refund`;
- `email.send_external`;
- `repo.merge_pr`.

## Confirmation Policy

Default policy:

- read tools: no confirmation;
- write tools: confirmation required unless explicitly exempted;
- dangerous tools: confirmation always required;
- destructive tools: confirmation plus elevated permission.

Confirmation should be shown in Telegram:

```text
[Assistant] I need confirmation before creating this event.
Action: act_123
Tool: calendar.create_event
Title: Planning block
Time: 2026-06-01 10:00-11:00

Reply with /confirm act_123 or /cancel act_123.
```

## Permission Scopes

Permissions should support:

- workspace scope;
- user scope;
- project scope;
- agent scope;
- tool scope.

Example:

```yaml
agent_id: personal_assistant
workspace_id: main
allowed_capabilities:
  - calendar.read
  - calendar.create_event
  - tasks.read
  - tasks.create
confirmation_required:
  - calendar.create_event
  - tasks.create
```

## Sensitive Data Handling

MCP results may include sensitive information. The renderer should not post raw tool output to Telegram.

Use summaries:

```text
[Assistant -> Docs] Searching internal docs for "Q3 roadmap".
[Docs -> Assistant] Found 4 matching documents. I will summarize the relevant points.
```

Avoid:

```text
Full raw document content pasted into Telegram.
```

## Audit Requirements

Every MCP call should record:

- `tool_call_id`;
- `agent_id`;
- `workspace_id`;
- optional `project_id`;
- capability name;
- raw MCP server/tool name;
- arguments hash or redacted arguments;
- result status;
- result summary;
- confirmation id if required;
- timestamps;
- error details.
