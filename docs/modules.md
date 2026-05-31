# Module Plan

The system should be built as separate modules so development can proceed incrementally.

## 1. Telegram Adapter

Purpose: connect Telegram groups to the backend.

Responsibilities:

- receive webhook updates;
- normalize Telegram messages;
- send rendered messages;
- edit messages for status updates;
- handle commands;
- map Telegram chat ids to workspaces;
- map Telegram user ids to internal users.

Initial deliverables:

- webhook endpoint;
- `sendMessage` wrapper;
- group chat registration;
- basic command handling for `/agents`, `/help`, `/confirm`, `/cancel`.

## 2. Event Log

Purpose: make all activity durable and inspectable.

Responsibilities:

- store inbound user messages;
- store agent messages;
- store agent-to-agent messages;
- store tool call requests and results;
- store confirmations;
- store failures and retries.

Initial deliverables:

- append-only event table;
- event ids;
- event types;
- correlation ids for one user request across multiple agent actions.

## 3. Agent Registry

Purpose: define virtual agents.

Responsibilities:

- load agent definitions from config or database;
- expose role, name, tools, memory scopes, and delegation permissions;
- expose optional per-agent model configuration;
- support enabling/disabling agents per workspace or project.

Initial deliverables:

- `personal_assistant` definition;
- config file format;
- runtime lookup by agent id.

## 4. Router

Purpose: decide which agent or workflow should handle each message.

Responsibilities:

- detect direct mentions;
- route default messages to the personal assistant;
- route confirmation replies;
- route project-specific messages;
- prevent accidental multi-agent storms.

Initial deliverables:

- default route to `personal_assistant`;
- direct mention routing, for example `@assistant`;
- confirmation routing by pending action id.

## 5. Agent Runtime

Purpose: run one agent turn and produce structured outputs.

Responsibilities:

- prepare model context;
- include role prompt and relevant memory;
- expose only allowed tools;
- parse structured agent actions;
- emit visible messages and internal actions.

Initial deliverables:

- one-turn assistant response;
- structured output schema;
- tool call request schema;
- visible thought/action separation.

Important: raw hidden chain-of-thought must not be posted. Instead, agents should publish concise operational messages like "I will check the calendar" or "I need confirmation before creating this event."

## 6. Conversation Protocol

Purpose: represent agent-to-agent interaction safely.

Responsibilities:

- create agent messages;
- create delegation requests;
- track accepted/completed/rejected work;
- limit recursion and fanout;
- render collaboration to Telegram.

Initial deliverables:

- `agent_message` event;
- `delegation_requested` event;
- `delegation_completed` event;
- max delegation depth setting.

## 7. Telegram Renderer

Purpose: turn internal events into user-readable group messages.

Responsibilities:

- format messages by agent;
- group noisy events;
- publish status updates;
- render tool calls at the right visibility level;
- keep Telegram readable.

Initial deliverables:

- basic message templates;
- per-event visibility levels;
- compact tool call rendering.

## 8. MCP Gateway

Purpose: provide controlled access to internal systems.

Responsibilities:

- configure MCP servers;
- list available tools;
- invoke tools;
- normalize tool results;
- enforce timeouts and retries;
- record all calls.

Initial deliverables:

- MCP server config format;
- tool registry;
- stub MCP provider for local development;
- call logging.

## 9. Policy Engine

Purpose: keep autonomy bounded.

Responsibilities:

- check whether an agent may use a tool;
- require confirmation for mutations;
- enforce workspace, project, and user scopes;
- redact sensitive outputs before Telegram rendering.

Initial deliverables:

- tool allowlist per agent;
- confirmation policy;
- mutation classification.

## 10. Memory Service

Purpose: provide durable and scoped context.

Responsibilities:

- store user preferences;
- store project facts;
- store summaries;
- store decisions;
- retrieve relevant memory for agent runs.

Initial deliverables:

- simple key-value memory;
- workspace-level memory;
- user-level memory;
- manual memory write action.

## 11. Project Workspace

Purpose: represent software projects and their assigned agents.

Responsibilities:

- project registry;
- project agent;
- specialist agent assignment;
- backlog/task integration;
- project-specific memory and permissions.

Initial deliverables:

- project config schema;
- project agent role;
- delegation to specialist agents.
