# Development Roadmap

## Phase 0: Documentation And Decisions

Outcome: architecture is clear enough to implement module by module.

Tasks:

- define system architecture;
- define Telegram visible interaction model;
- define initial agent model;
- define MCP permission model;
- define data model;
- choose initial backend stack.

Status: documented.

## Phase 1: Telegram Runtime

Outcome: a Telegram group can talk to one backend bot.

Tasks:

- create backend project;
- add Telegram webhook;
- register one Telegram group as a workspace;
- store inbound Telegram messages;
- send bot responses;
- implement `/agents`, `/help`, `/confirm`, `/cancel`.

Acceptance criteria:

- user sends a message in the group;
- backend receives and stores it;
- bot replies in the group;
- message appears in event log.

## Phase 2: Personal Assistant Runtime

Outcome: one virtual assistant can answer and publish visible operational messages.

Tasks:

- create `personal_assistant` agent config;
- add router defaulting to the assistant;
- add agent runtime;
- add Telegram renderer;
- store agent runs and events;
- add structured agent output.

Acceptance criteria:

- user asks a question;
- assistant acknowledges;
- assistant answers;
- event log contains request, agent run, and response.

## Phase 3: MCP Gateway And Tool Stubs

Outcome: assistant can call stubbed capabilities through the same pathway real MCP tools will use.

Tasks:

- add MCP gateway interface;
- add local stub provider;
- define capability registry;
- log tool calls;
- render compact tool call messages.

Acceptance criteria:

- assistant requests `calendar.read`;
- gateway returns stub calendar data;
- Telegram shows compact tool call and result summary.

## Phase 4: Confirmation Flow

Outcome: write actions require approval in Telegram.

Tasks:

- add confirmation records;
- add pending action ids;
- implement `/confirm <action_id>`;
- implement `/cancel <action_id>`;
- execute approved actions through MCP gateway;
- expire old confirmations.

Acceptance criteria:

- assistant proposes `calendar.create_event`;
- Telegram shows confirmation request;
- user confirms;
- tool call is executed;
- assistant reports completion.

## Phase 5: Real MCP Integrations

Outcome: internal systems become available through controlled MCP tools.

Tasks:

- configure first real MCP server;
- map raw tools to capabilities;
- implement per-agent tool allowlists;
- redact sensitive results;
- add timeouts and retries.

Acceptance criteria:

- assistant reads real internal data through MCP;
- Telegram receives only safe summaries;
- all MCP calls are auditable.

## Phase 6: Agent-To-Agent Protocol

Outcome: visible collaboration exists even before project agents are fully built.

Tasks:

- add delegation events;
- add agent-to-agent message schema;
- add max delegation depth;
- render delegation in Telegram;
- add test specialist agent with no external tools.

Acceptance criteria:

- assistant delegates a research/check task to another agent;
- Telegram shows request, acceptance, and completion;
- event log links all events through one request id.

## Phase 6.5: Assistant Decision Router

Outcome: free-form user text is routed by Assistant/model decisions, not by keyword matching.

Tasks:

- remove ad hoc substring routing from `handle_message`;
- pass the registered agent list to Assistant as routing context;
- make Assistant return structured actions such as `answer`, `delegate`, `schedule_intent`, and `ask_clarification`;
- execute structured actions through the orchestrator;
- persist deferred intent payloads for Planner;
- when Planner fires, return the stored intent to Assistant instead of sending the raw reminder directly to the user.

Acceptance criteria:

- "Подскажи погоду в Питере" delegates to Weather because Assistant chose Weather;
- "проверь погоду в питере через час" delegates first to Planner;
- one hour later Planner returns the deferred intent to Assistant;
- Assistant then delegates to Weather and sends the final answer;
- no natural-language routing depends on hardcoded keyword checks.

## Phase 7: Project Agents

Outcome: each software project can have its own coordinating agent.

Tasks:

- add project registry;
- add project agent template;
- route project mentions;
- add project memory scope;
- allow project agents to delegate to specialists;
- add project status command.

Acceptance criteria:

- user creates or configures a project;
- project agent appears in `/agents`;
- project agent can delegate a task;
- Telegram shows the project coordination.

## Phase 8: Specialist Agents

Outcome: project agents can coordinate developer, designer, QA, and release agents.

Tasks:

- define specialist roles;
- assign tools and permissions;
- connect repository/task/design/test MCPs;
- add task handoff lifecycle;
- add project summary reports.

Acceptance criteria:

- project agent decomposes a request;
- specialist agents respond visibly;
- final project response includes consolidated results.
