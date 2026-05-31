from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResult:
    capability: str
    summary: str
    data: dict


class McpGatewayStub:
    """Placeholder for future MCP integrations."""

    def list_capabilities(self) -> list[str]:
        return [
            "calendar.read",
            "calendar.create_event",
            "tasks.read",
            "tasks.create",
            "docs.search",
            "agent_prompt.prepare",
            "weather.forecast",
            "reminder.create",
            "reminder.list",
            "telegram.send_message",
            "python.code_review",
            "python.design",
            "python.debug",
            "python.explain",
            "github.repo_read",
            "github.file_read",
            "github.file_write",
            "github.pr_open",
            "github.pr_merge",
        ]

    def read_status(self) -> ToolResult:
        return ToolResult(
            capability="mcp.status",
            summary="MCP gateway is running in stub mode. No internal systems are connected yet.",
            data={"mode": "stub"},
        )
