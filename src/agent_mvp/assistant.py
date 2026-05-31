from __future__ import annotations

import json
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass

from .agent_registry import PERSONAL_ASSISTANT_ID, format_assistant_agent_context
from .config import Config


ASSISTANT_ID = PERSONAL_ASSISTANT_ID
ASSISTANT_NAME = "Assistant"


SYSTEM_PROMPT = """\
You are the user's personal assistant inside a Telegram group.

Product context:
- The current workspace has several visible virtual agents coordinated by Assistant.
- The system will later include project agents and specialist agents.
- Telegram must show concise operational interaction between agents.
- The assistant is the default user-facing coordinator.
- When a request matches a specialist agent, delegate the task and then summarize the specialist result to the user.

Your responsibilities:
- answer the user's questions;
- help plan their schedule;
- prepare high-quality prompts for future agents;
- ask clarifying questions when needed;
- avoid pretending that unavailable tools are connected;
- do not claim that you delegated to another agent unless the orchestration layer actually provided that specialist result;
- be concise, practical, and warm;
- respond in the same language as the user unless asked otherwise.

If the user asks for weather, reminders, or another specialist-owned task and no specialist result is present in your context, do not simulate the specialist. Say that the request should be delegated by the router or ask the user to use the explicit specialist command.

When asked to prepare a prompt for another agent:
- produce a reusable role prompt;
- include responsibilities, inputs, outputs, constraints, and interaction style;
- make the prompt suitable for a future multi-agent software development workflow.

Do not reveal hidden chain-of-thought. You may describe visible operational steps briefly.
"""


@dataclass(frozen=True)
class AssistantReply:
    public_messages: list[str]
    internal_summary: str


@dataclass(frozen=True)
class AssistantDecision:
    action: str
    text: str
    reason: str = ""


class AssistantRuntime:
    def __init__(self, config: Config) -> None:
        self.config = config

    def respond(self, user_text: str, display_user: str) -> AssistantReply:
        if self.config.openai_enabled:
            return self._respond_with_openai(user_text, display_user)
        return self._respond_offline(user_text, display_user)

    def decide(self, user_text: str) -> AssistantDecision:
        if not self.config.openai_enabled:
            return AssistantDecision(action="fallback", text=user_text, reason="OpenAI is disabled.")
        return self._decide_with_openai(user_text)

    def _decide_with_openai(self, user_text: str) -> AssistantDecision:
        assert self.config.openai_api_key is not None
        assert self.config.openai_model is not None

        system_prompt = textwrap.dedent(
            f"""
            You are the routing brain for the user's personal assistant.
            Decide what the assistant should do with this Telegram message.

            Available actions:
            - answer: Assistant should answer directly.
            - delegate_weather: Assistant should delegate now to Weather.
            - delegate_python_developer: Assistant should delegate now to Senior Python Developer.
            - schedule_intent: Assistant should delegate to Planner to return this intent later.
            - ask_clarification: Assistant should ask a clarifying question.

            Rules:
            - If the user asks to do something later, after a delay, or at a future time, choose schedule_intent.
            - For schedule_intent, text must be the task to return later, without the scheduling phrase.
            - If the user asks for current weather now, choose delegate_weather.
            - If the user asks for Python implementation, Python code review, Python debugging, backend architecture in Python, or Python explanation, choose delegate_python_developer.
            - Do not rely on keyword matching; infer the user's intent.
            - Return JSON only, with keys: action, text, reason.

            {format_assistant_agent_context()}
            """
        ).strip()
        payload = {
            "model": self.config.openai_model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
            raw_text = self._extract_response_text(data)
            parsed = json.loads(raw_text)
            action = str(parsed.get("action", "answer"))
            text = str(parsed.get("text", user_text)).strip() or user_text
            reason = str(parsed.get("reason", ""))
            if action not in {
                "answer",
                "delegate_weather",
                "delegate_python_developer",
                "schedule_intent",
                "ask_clarification",
            }:
                action = "answer"
            return AssistantDecision(action=action, text=text, reason=reason)
        except Exception as exc:
            return AssistantDecision(action="fallback", text=user_text, reason=f"Decision failed: {exc}")

    def _respond_with_openai(self, user_text: str, display_user: str) -> AssistantReply:
        assert self.config.openai_api_key is not None
        assert self.config.openai_model is not None

        system_prompt = f"{SYSTEM_PROMPT}\n\n{format_assistant_agent_context()}"
        payload = {
            "model": self.config.openai_model,
            "input": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": f"Telegram user {display_user} wrote:\n{user_text}",
                },
            ],
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.openai_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return AssistantReply(
                public_messages=[
                    "[Assistant] Я попытался обратиться к модели, но получил ошибку API.",
                    f"[Assistant] Детали: {error_body[:900]}",
                ],
                internal_summary=f"OpenAI HTTP error {exc.code}",
            )
        except OSError as exc:
            return AssistantReply(
                public_messages=[
                    "[Assistant] Сейчас не получилось подключиться к OpenAI API.",
                    f"[Assistant] Техническая причина: {exc}",
                ],
                internal_summary=f"OpenAI connection error: {exc}",
            )

        data = json.loads(body)
        text = self._extract_response_text(data)
        if not text:
            text = "Я получил пустой ответ от модели. Событие сохранено, можно повторить запрос."

        return AssistantReply(
            public_messages=[f"[Assistant] {text}"],
            internal_summary="Answered through OpenAI Responses API.",
        )

    def _extract_response_text(self, data: dict) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"].strip()

        chunks: list[str] = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    chunks.append(str(content["text"]))
        return "\n".join(chunks).strip()

    def _respond_offline(self, user_text: str, display_user: str) -> AssistantReply:
        normalized = user_text.strip()
        lower = normalized.lower()

        if lower.startswith("/prompt_for_agent"):
            prompt = self._offline_agent_prompt(normalized.removeprefix("/prompt_for_agent").strip())
            return AssistantReply(
                public_messages=[
                    "[Assistant] Подготовил черновик промпта для будущего агента.",
                    f"[Assistant]\n{prompt}",
                ],
                internal_summary="Prepared offline agent prompt draft.",
            )

        return AssistantReply(
            public_messages=[
                "[Assistant] Принял запрос. Сейчас я работаю в offline-режиме, потому что OPENAI_API_KEY или OPENAI_MODEL не настроены.",
                (
                    "[Assistant] Я уже могу принимать сообщения из Telegram, вести event log и готов к подключению модели. "
                    "После заполнения OpenAI-переменных я начну отвечать полноценно."
                ),
                (
                    f"[Assistant] Последний запрос от {display_user}: {normalized[:500]}"
                ),
            ],
            internal_summary="Offline fallback response.",
        )

    def _offline_agent_prompt(self, request: str) -> str:
        if not request:
            request = "role: future software project specialist; task: support the project agent"

        return textwrap.dedent(
            f"""
            Role prompt draft

            Context:
            You are a specialist agent in a Telegram-visible multi-agent software development workspace.

            Requested role/task:
            {request}

            Responsibilities:
            - accept clear delegations from the project agent or personal assistant;
            - ask concise clarifying questions when requirements are incomplete;
            - produce practical outputs that another agent or human can use;
            - report progress and final results in Telegram-visible operational language;
            - avoid changing external systems unless an approved tool and confirmation are provided.

            Inputs:
            - task description;
            - project context;
            - relevant event history;
            - allowed MCP capabilities.

            Outputs:
            - short acknowledgement;
            - execution plan when useful;
            - final result with assumptions, risks, and next actions.

            Constraints:
            - do not reveal hidden chain-of-thought;
            - do not claim access to tools that are not explicitly available;
            - keep messages concise enough for a group chat;
            - escalate decisions that need user confirmation.
            """
        ).strip()
