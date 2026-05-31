from __future__ import annotations

from dataclasses import dataclass


PERSONAL_ASSISTANT_ID = "personal_assistant"
WEATHER_ASSISTANT_ID = "weather_assistant"
PLANNER_ASSISTANT_ID = "planner_assistant"
SENIOR_PYTHON_DEVELOPER_ID = "senior_python_developer"


@dataclass(frozen=True)
class AgentDefinition:
    id: str
    display_name: str
    description: str
    commands: tuple[str, ...]
    capabilities: tuple[str, ...]
    receives_delegations: bool
    model_env: str | None = None
    api_key_env: str | None = None
    base_url_env: str | None = None

    @property
    def label(self) -> str:
        return self.display_name


AGENTS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        id=PERSONAL_ASSISTANT_ID,
        display_name="Assistant",
        description="Личный помощник: ответы, координация, подготовка промптов для будущих агентов.",
        commands=("/prompt_for_agent",),
        capabilities=("agent_prompt.prepare",),
        receives_delegations=False,
    ),
    AgentDefinition(
        id=WEATHER_ASSISTANT_ID,
        display_name="Weather",
        description="Ассистент погоды: получает прогноз через публичный weather provider.",
        commands=("/weather",),
        capabilities=("weather.forecast",),
        receives_delegations=True,
    ),
    AgentDefinition(
        id=PLANNER_ASSISTANT_ID,
        display_name="Planner",
        description="Планировщик: создаёт и отправляет Telegram-напоминания.",
        commands=("/remind", "/reminders"),
        capabilities=("reminder.create", "reminder.list", "telegram.send_message"),
        receives_delegations=True,
    ),
    AgentDefinition(
        id=SENIOR_PYTHON_DEVELOPER_ID,
        display_name="Senior Python Developer",
        description="Старший Python-разработчик: проектирует, ревьюит и объясняет Python-код и backend-решения.",
        commands=("/python_dev", "/python_pr"),
        capabilities=(
            "python.code_review",
            "python.design",
            "python.debug",
            "python.explain",
            "github.repo_read",
            "github.pr_open",
        ),
        receives_delegations=True,
        model_env="PYTHON_DEVELOPER_MODEL",
        api_key_env="PYTHON_DEVELOPER_API_KEY",
        base_url_env="PYTHON_DEVELOPER_BASE_URL",
    ),
)


def get_agent(agent_id: str) -> AgentDefinition:
    for agent in AGENTS:
        if agent.id == agent_id:
            return agent
    raise KeyError(f"Unknown agent: {agent_id}")


def format_agents() -> str:
    lines = ["[Assistant] Активные агенты:"]
    for agent in AGENTS:
        commands = ", ".join(agent.commands) if agent.commands else "без прямых команд"
        delegation = "принимает делегирование" if agent.receives_delegations else "координирующий агент"
        model = f" Модель: `{agent.model_env}`." if agent.model_env else ""
        lines.append(
            f"- {agent.display_name} (`{agent.id}`): {agent.description} "
            f"Команды: {commands}. Роль: {delegation}.{model}"
        )
    return "\n".join(lines)


def format_assistant_agent_context() -> str:
    lines = [
        "Available virtual agents. The assistant should delegate specialist work instead of doing it directly:",
    ]
    for agent in AGENTS:
        if agent.id == PERSONAL_ASSISTANT_ID:
            continue
        commands = ", ".join(agent.commands)
        capabilities = ", ".join(agent.capabilities)
        model_note = ""
        if agent.model_env:
            model_note = f" Model env: {agent.model_env}; API key env: {agent.api_key_env}."
        lines.append(
            f"- {agent.display_name} ({agent.id}): {agent.description} "
            f"Commands: {commands}. Capabilities: {capabilities}.{model_note}"
        )
    return "\n".join(lines)
