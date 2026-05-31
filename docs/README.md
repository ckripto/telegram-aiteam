# Multi-Agent Telegram Workspace

This documentation describes an architecture for a Telegram-based multi-agent workspace.

The system starts with one visible personal assistant in a Telegram group and grows into a project-oriented agent organization where project agents can coordinate specialist agents for software development, design, QA, research, operations, and other roles.

The key product requirement is that the Telegram group should show the interaction between agents. The group is not only a chat interface for the user. It is also the visible activity stream where agents announce intent, delegate work, ask each other for input, report progress, request confirmation, and publish results.

## Documents

- [Architecture Overview](./architecture.md)
- [Module Plan](./modules.md)
- [Telegram Interaction Model](./telegram-interaction.md)
- [Agents And Roles](./agents.md)
- [MCP And Permissions](./mcp-permissions.md)
- [Memory And Data Model](./memory-data.md)
- [Development Roadmap](./roadmap.md)
- [Adding New Agents](./adding-agents.md)

## Design Principles

1. Use one real Telegram bot and many virtual agents inside the backend.
2. Keep agent interaction visible in Telegram by default.
3. Separate agent reasoning, tool access, memory, permissions, and Telegram rendering.
4. Require explicit confirmation for actions that change external systems.
5. Treat MCP tools as capability providers with strict per-agent permissions.
6. Make every autonomous action traceable through durable events.
7. Start with a narrow personal assistant, then add project agents and specialist agents.

## Initial Workspace

The first version should support:

- one Telegram group;
- one Telegram bot;
- multiple virtual agents registered in the agent registry;
- user questions and scheduling requests;
- visible assistant planning messages in the Telegram group;
- MCP tool discovery and stubbed tool calls;
- confirmation flow before calendar/task mutations;
- durable event log for all messages, agent decisions, tool calls, and confirmations.
- optional per-agent model credentials for specialist agents.
