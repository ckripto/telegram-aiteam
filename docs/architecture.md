# Architecture Overview

## Goal

Build a multi-agent workspace where Telegram is the shared room, the backend is the orchestrator, and MCP servers provide controlled access to internal systems.

The architecture should support two stages:

1. Personal assistant stage: one assistant plans schedule, answers questions, and uses approved MCP tools.
2. Project workspace stage: each software project has a project agent that can delegate work to specialist agents and report all coordination in Telegram.

## High-Level Architecture

```text
Telegram Group
    |
Telegram Bot Webhook
    |
API Gateway
    |
Agent Orchestrator
    |
    +-- Router
    +-- Agent Runtime
    +-- Conversation Protocol
    +-- Policy Engine
    +-- Memory Service
    +-- Event Log
    +-- Telegram Renderer
    |
MCP Gateway
    |
Internal Systems
```

## Core Idea

There should be one actual Telegram bot account. Inside the backend, each agent is virtual and has:

- stable agent id;
- display name;
- role prompt;
- allowed tools;
- memory scopes;
- delegation permissions;
- visibility settings;
- confirmation policy.
- optional dedicated model configuration.

Telegram messages are rendered as if multiple agents are present:

```text
[Planner] I will check today's calendar before suggesting a schedule.
[Planner -> Calendar MCP] Reading events for 2026-05-31.
[Planner] Found 3 fixed meetings. I suggest moving focused work to 14:00-16:00.
```

## Main Runtime Flow

1. Telegram sends a group message to the webhook.
2. API Gateway authenticates and normalizes the update.
3. Router decides whether this message is:
   - a direct user request;
   - an agent mention;
   - a confirmation response;
   - a background status update trigger;
   - an internal command.
4. Agent Orchestrator creates an event and selects one or more agents.
5. Agent Runtime runs the selected agent with relevant context and allowed tools.
6. Tool requests go through Policy Engine and MCP Gateway.
7. Every meaningful action is written to Event Log.
8. Telegram Renderer publishes visible agent messages into the group.

## Runtime Boundaries

### Telegram Bot Layer

Responsible for:

- receiving updates;
- sending messages;
- editing status messages;
- mapping Telegram users/chats to workspace users and rooms;
- rate limiting Telegram output.

Not responsible for:

- agent reasoning;
- permissions;
- direct MCP access;
- business logic.

### Agent Orchestrator

Responsible for:

- routing;
- selecting agents;
- managing agent-to-agent interactions;
- collecting context;
- enforcing workflow state;
- producing events;
- requesting Telegram rendering.

The personal assistant is the default user-facing coordinator. When a message clearly belongs to a specialist, the orchestrator should make the delegation visible, collect the specialist result, and let Assistant publish the final answer.

Free-form user requests must not be routed by keyword matching such as checking whether the text contains "weather" or "погод". The routing decision belongs to Assistant or to a model-backed intent router that receives the registered agent list and returns a structured decision.

Allowed routing signals:

- explicit commands, for example `/weather` or `/remind`;
- explicit agent mentions;
- pending confirmation/action ids;
- model/Assistant delegation decisions based on the agent registry.

Disallowed routing signals:

- ad hoc substring checks over user text;
- hardcoded keyword lists for natural-language intent;
- specialist agents hidden outside the agent registry.

This keeps future requests like "проверь погоду в питере через час" composable: Assistant can decide that the first step is a delayed Planner task, and Planner can later return the deferred intent to Assistant instead of trying to finish the whole task by itself.

### Agent Runtime

Responsible for:

- constructing model requests;
- applying agent role and instructions;
- selecting the correct model credentials for the current agent;
- producing structured actions;
- calling tools through the orchestrator;
- returning messages and state updates.

The runtime should not call internal systems directly.

Agents may use different AI models and different API tokens. Assistant can use the default `OPENAI_API_KEY` and `OPENAI_MODEL`, while a specialist such as Senior Python Developer can use `PYTHON_DEVELOPER_API_KEY`, `PYTHON_DEVELOPER_MODEL`, and `PYTHON_DEVELOPER_BASE_URL`. The registry should make those settings visible so Assistant knows the specialist exists, while the specialist runtime owns the actual credential usage.

### MCP Gateway

Responsible for:

- connecting to configured MCP servers;
- listing tools/resources;
- invoking tools;
- normalizing results;
- enforcing timeouts;
- recording tool calls.

### Policy Engine

Responsible for:

- per-agent tool allowlists;
- user consent checks;
- confirmation requirements;
- data visibility rules;
- project-level permission scopes.

## Visible Agent Collaboration

Agent collaboration should be represented as events and rendered to Telegram.

Example:

```text
[Project Alpha] I need an implementation estimate for calendar sync.
[Project Alpha -> Backend Dev] Please inspect the current API design and estimate backend effort.
[Backend Dev] Accepted. I will review the API module and report back.
[Backend Dev -> Project Alpha] Estimate: 1.5 days, main risk is OAuth token refresh.
[Project Alpha] I will add this to the implementation plan.
```

This is important because the user wants to observe how agents coordinate, not only receive the final answer.

## Persistence

The system needs durable persistence from the beginning:

- Telegram messages;
- normalized events;
- agent runs;
- tool calls;
- confirmations;
- memory records;
- project records;
- agent registry;
- permissions.

SQLite is acceptable for local development. Postgres is preferred for production.

## Recommended Initial Stack

The architecture is language-neutral. A practical first implementation can use:

- TypeScript backend;
- Telegraf or grammY for Telegram;
- Postgres or SQLite;
- OpenAI API for model calls;
- MCP TypeScript SDK;
- background jobs through BullMQ, pg-boss, or a simple internal queue for local development.
