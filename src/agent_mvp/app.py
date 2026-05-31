from __future__ import annotations

import signal
import sys
import time
from zoneinfo import ZoneInfo

from .agent_registry import PERSONAL_ASSISTANT_ID
from .assistant import AssistantRuntime
from .config import Config, load_config
from .github_gateway import GitHubGateway
from .mcp_stub import McpGatewayStub
from .python_developer import SeniorPythonDeveloperRuntime
from .reminders import ReminderParser
from .routing import MessageRouter
from .specialist_workflows import SpecialistWorkflows
from .storage import EventStore
from .telegram import TelegramClient, TelegramMessage, parse_message
from .telegram_rendering import TelegramEventRenderer
from .weather import WeatherService


class AgentWorkspaceApp:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.telegram = TelegramClient(config.telegram_bot_token)
        self.store = EventStore(config.database_path)
        self.assistant = AssistantRuntime(config)
        self.python_developer = SeniorPythonDeveloperRuntime(config)
        self.github = GitHubGateway(config)
        self.mcp = McpGatewayStub()
        self.weather = WeatherService()
        self.reminder_parser = ReminderParser(config.local_timezone)
        self.timezone = ZoneInfo(config.local_timezone)
        self.renderer = TelegramEventRenderer(self)
        self.workflows = SpecialistWorkflows(self, self.renderer)
        self.router = MessageRouter(self, self.renderer)
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run_polling(self) -> None:
        offset: int | None = None
        print("Agent workspace started. Press Ctrl+C to stop.", flush=True)
        print(f"Database: {self.config.database_path}", flush=True)
        print(f"OpenAI enabled: {self.config.openai_enabled}", flush=True)
        print(f"Senior Python Developer enabled: {self.config.python_developer_enabled}", flush=True)
        print(f"GitHub enabled: {self.config.github_enabled}", flush=True)

        while self._running:
            try:
                updates = self.telegram.get_updates(offset=offset, timeout=self.config.poll_timeout_seconds)
                for update in updates:
                    offset = int(update["update_id"]) + 1
                    message = parse_message(update)
                    if message is not None:
                        self.handle_message(message)
                self.process_due_reminders()
            except KeyboardInterrupt:
                self.stop()
            except Exception as exc:
                print(f"Polling error: {exc}", file=sys.stderr, flush=True)
                time.sleep(self.config.poll_interval_seconds)

    def handle_message(self, message: TelegramMessage) -> None:
        self.router.handle_message(message)

    def handle_command(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> bool:
        return self.router.handle_command(message, text, request_id, conversation_id)

    def handle_python_file_read(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.handle_python_file_read(message, text, request_id, conversation_id)

    def handle_python_file_change(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.handle_python_file_change(message, text, request_id, conversation_id)

    def handle_python_merge_pr(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.handle_python_merge_pr(message, text, request_id, conversation_id)

    def handle_python_pull_request(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.handle_python_pull_request(message, text, request_id, conversation_id)

    def delegate_python_developer_from_assistant(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.delegate_python_developer_from_assistant(message, text, request_id, conversation_id)

    def delegate_python_developer_to_chat(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
        reply_to_message_id: int | None = None,
        final_prefix: str = "[Assistant] Senior Python Developer вернул результат:",
    ) -> None:
        self.workflows.delegate_python_developer_to_chat(
            chat_id=chat_id,
            text=text,
            request_id=request_id,
            conversation_id=conversation_id,
            reply_to_message_id=reply_to_message_id,
            final_prefix=final_prefix,
        )

    def delegate_weather_from_assistant(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.delegate_weather_from_assistant(message, text, request_id, conversation_id)

    def delegate_weather_to_chat(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
        reply_to_message_id: int | None = None,
        final_prefix: str = "[Assistant] По данным Weather:",
    ) -> None:
        self.workflows.delegate_weather_to_chat(
            chat_id=chat_id,
            text=text,
            request_id=request_id,
            conversation_id=conversation_id,
            reply_to_message_id=reply_to_message_id,
            final_prefix=final_prefix,
        )

    def delegate_reminder_from_assistant(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.delegate_reminder_from_assistant(message, text, request_id, conversation_id)

    def handle_weather(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
        delegated: bool = False,
    ) -> str:
        return self.workflows.handle_weather(chat_id, text, request_id, conversation_id, delegated)

    def handle_reminder(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
        delegated: bool = False,
    ) -> str | None:
        return self.workflows.handle_reminder(message, text, request_id, conversation_id, delegated)

    def handle_reminders_list(
        self,
        message: TelegramMessage,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.handle_reminders_list(message, request_id, conversation_id)

    def process_due_reminders(self) -> None:
        self.workflows.process_due_reminders()

    def handle_deferred_intent(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.workflows.handle_deferred_intent(chat_id, text, request_id, conversation_id)

    def extract_weather_location(self, text: str) -> str:
        return self.workflows.extract_weather_location(text)

    def normalize_location(self, location: str) -> str:
        return self.workflows.normalize_location(location)

    def looks_like_weather_request(self, text: str) -> bool:
        return self.workflows.looks_like_weather_request(text)

    def looks_like_reminder_request(self, text: str) -> bool:
        return self.workflows.looks_like_reminder_request(text)

    def can_parse_reminder(self, text: str) -> bool:
        return self.workflows.can_parse_reminder(text)

    def extract_command_payload(self, text: str, command: str) -> str:
        return self.workflows.extract_command_payload(text, command)

    def add_developer_project_context(self, task: str) -> str:
        return self.workflows.add_developer_project_context(task)

    def should_open_pr_from_developer_task(self, task: str) -> bool:
        return self.workflows.should_open_pr_from_developer_task(task)

    def try_handle_developer_pr_task(
        self,
        chat_id: int,
        task: str,
        user_task: str,
        request_id: str,
        conversation_id: str,
    ) -> bool:
        return self.workflows.try_handle_developer_pr_task(chat_id, task, user_task, request_id, conversation_id)

    def parse_python_pr_command(self, text: str) -> tuple[str, str, str, str] | None:
        return self.workflows.parse_python_pr_command(text)

    def parse_python_file_command(self, text: str) -> tuple[str, str, str] | None:
        return self.workflows.parse_python_file_command(text)

    def parse_python_change_file_command(self, text: str) -> tuple[str, str, str, str, str] | None:
        return self.workflows.parse_python_change_file_command(text)

    def parse_python_merge_pr_command(self, text: str) -> tuple[str, int] | None:
        return self.workflows.parse_python_merge_pr_command(text)

    def emit_agent_message(
        self,
        chat_id: int,
        request_id: str,
        conversation_id: str,
        text: str,
        reply_to_message_id: int | None = None,
        agent_id: str = PERSONAL_ASSISTANT_ID,
    ) -> None:
        self.renderer.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            agent_id=agent_id,
        )

    def emit_delegation_event(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task: str,
        request_id: str,
        conversation_id: str,
        chat_id: int,
    ) -> None:
        self.renderer.emit_delegation_event(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            task=task,
            request_id=request_id,
            conversation_id=conversation_id,
            chat_id=chat_id,
        )


def main() -> None:
    config = load_config()
    app = AgentWorkspaceApp(config)

    def handle_signal(_signum: int, _frame: object) -> None:
        app.stop()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    app.run_polling()


AgentMvpApp = AgentWorkspaceApp
