from __future__ import annotations

from typing import Any

from .agent_registry import PERSONAL_ASSISTANT_ID, format_agents
from .events import Event, new_id
from .telegram import TelegramMessage


class MessageRouter:
    def __init__(self, app: Any, renderer: Any) -> None:
        self.app = app
        self.renderer = renderer

    def handle_message(self, message: TelegramMessage) -> None:
        if self.app.config.telegram_allowed_chat_id is not None:
            if message.chat_id != self.app.config.telegram_allowed_chat_id:
                print(f"Ignoring message from unauthorized chat {message.chat_id}", flush=True)
                return

        request_id = new_id("req")
        conversation_id = f"tg_{message.chat_id}"
        self.app.store.append(
            Event.create(
                event_type="telegram_message_received",
                actor_type="user",
                actor_id=str(message.user_id or "unknown"),
                visibility="public",
                payload={
                    "text": message.text,
                    "display_user": message.display_user,
                },
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=message.chat_id,
                telegram_message_id=message.message_id,
            )
        )

        text = message.text.strip()
        if text.startswith("/"):
            handled = self.handle_command(message, text, request_id, conversation_id)
            if handled:
                return

        decision = self.app.assistant.decide(text)
        if decision.action == "schedule_intent":
            self.app.delegate_reminder_from_assistant(message, text, request_id, conversation_id)
            return

        if decision.action == "delegate_weather":
            self.app.delegate_weather_from_assistant(message, decision.text, request_id, conversation_id)
            return

        if decision.action == "delegate_python_developer":
            self.app.delegate_python_developer_from_assistant(message, decision.text, request_id, conversation_id)
            return

        if decision.action == "ask_clarification":
            self.renderer.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Assistant] {decision.text}",
                reply_to_message_id=message.message_id,
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        if decision.action == "fallback":
            if self.app.can_parse_reminder(text):
                self.app.delegate_reminder_from_assistant(message, text, request_id, conversation_id)
                return

            if self.app.looks_like_weather_request(text):
                self.app.delegate_weather_from_assistant(message, text, request_id, conversation_id)
                return

        self.renderer.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Assistant] Принял запрос. Разберу его как личный помощник.",
            reply_to_message_id=message.message_id,
        )

        reply = self.app.assistant.respond(text, message.display_user)
        self.app.store.append(
            Event.create(
                event_type="agent_run_completed",
                actor_type="agent",
                actor_id=PERSONAL_ASSISTANT_ID,
                visibility="private",
                payload={"summary": reply.internal_summary},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=message.chat_id,
            )
        )

        for public_text in reply.public_messages:
            self.renderer.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=public_text,
            )

    def handle_command(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> bool:
        command = text.split(maxsplit=1)[0].split("@", 1)[0].lower()

        if command == "/help":
            self.renderer.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    "[Assistant] Доступные команды:\n"
                    "/help - справка\n"
                    "/agents - список виртуальных агентов\n"
                    "/status - состояние runtime\n"
                    "/weather <город> - спросить ассистента погоды\n"
                    "/remind <время> <текст> - попросить планировщика напомнить\n"
                    "/reminders - показать ближайшие напоминания\n"
                    "/python_dev <задача> - делегировать Senior Python Developer\n"
                    "/python_pr [repo] <head> <base> <title> - открыть draft PR через Senior Python Developer\n"
                    "/python_file [repo] <ref> <path> - прочитать файл из GitHub\n"
                    "/python_change_file [repo] <base> <branch> <path> <task> - изменить файл через PR\n"
                    "/python_merge_pr [repo] <number> CONFIRM - смержить PR после прямого указания\n"
                    "/prompt_for_agent <role>: <task> - подготовить промпт для будущего агента\n\n"
                    "Примеры:\n"
                    "/weather Moscow\n"
                    "/remind через 10 минут проверить сборку\n"
                    "/python_dev спроектируй FastAPI endpoint для задач\n"
                    "/python_pr feature-branch main Добавить GitHub skill\n"
                    "/python_file main README.md\n"
                    "/python_change_file main codex/readme-update README.md Добавь раздел запуска\n"
                    "/remind завтра 09:30 написать план дня"
                ),
                reply_to_message_id=message.message_id,
            )
            return True

        if command == "/agents":
            self.renderer.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=format_agents(),
                reply_to_message_id=message.message_id,
            )
            return True

        if command == "/status":
            tool_status = self.app.mcp.read_status()
            openai_status = "enabled" if self.app.config.openai_enabled else "offline fallback"
            self.renderer.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    "[Assistant] Статус runtime:\n"
                    f"- chat_id: {message.chat_id}\n"
                    f"- OpenAI runtime: {openai_status}\n"
                    f"- Senior Python Developer runtime: {'enabled' if self.app.config.python_developer_enabled else 'offline fallback'}\n"
                    f"- GitHub capability: {'enabled' if self.app.config.github_enabled else 'not configured'}\n"
                    f"- GitHub default repo: {self.app.config.github_default_repo or 'not configured'}\n"
                    f"- event log: {self.app.store.count_events()} events\n"
                    f"- timezone: {self.app.config.local_timezone}\n"
                    f"- weather default: {self.app.config.weather_default_location}\n"
                    f"- MCP: {tool_status.summary}"
                ),
                reply_to_message_id=message.message_id,
            )
            return True

        if command == "/prompt_for_agent":
            return False

        if command == "/weather":
            self.app.delegate_weather_from_assistant(message, text, request_id, conversation_id)
            return True

        if command == "/remind":
            self.app.delegate_reminder_from_assistant(message, text, request_id, conversation_id)
            return True

        if command == "/reminders":
            self.app.handle_reminders_list(message, request_id, conversation_id)
            return True

        if command == "/python_dev":
            self.app.delegate_python_developer_from_assistant(message, text, request_id, conversation_id)
            return True

        if command == "/python_pr":
            self.app.handle_python_pull_request(message, text, request_id, conversation_id)
            return True

        if command == "/python_file":
            self.app.handle_python_file_read(message, text, request_id, conversation_id)
            return True

        if command == "/python_change_file":
            self.app.handle_python_file_change(message, text, request_id, conversation_id)
            return True

        if command == "/python_merge_pr":
            self.app.handle_python_merge_pr(message, text, request_id, conversation_id)
            return True

        return False
