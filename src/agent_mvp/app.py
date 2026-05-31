from __future__ import annotations

import signal
import sys
import time
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from .agent_registry import (
    PERSONAL_ASSISTANT_ID,
    PLANNER_ASSISTANT_ID,
    SENIOR_PYTHON_DEVELOPER_ID,
    WEATHER_ASSISTANT_ID,
    format_agents,
)
from .assistant import AssistantRuntime
from .config import Config, load_config
from .events import Event, new_id, utc_now
from .github_gateway import GitHubGateway
from .mcp_stub import McpGatewayStub
from .python_developer import SeniorPythonDeveloperRuntime
from .reminders import ReminderParser
from .storage import EventStore
from .telegram import TelegramClient, TelegramMessage, parse_message
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
        if self.config.telegram_allowed_chat_id is not None:
            if message.chat_id != self.config.telegram_allowed_chat_id:
                print(f"Ignoring message from unauthorized chat {message.chat_id}", flush=True)
                return

        request_id = new_id("req")
        conversation_id = f"tg_{message.chat_id}"
        self.store.append(
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

        decision = self.assistant.decide(text)
        if decision.action == "schedule_intent":
            self.delegate_reminder_from_assistant(message, text, request_id, conversation_id)
            return

        if decision.action == "delegate_weather":
            self.delegate_weather_from_assistant(message, decision.text, request_id, conversation_id)
            return

        if decision.action == "delegate_python_developer":
            self.delegate_python_developer_from_assistant(message, decision.text, request_id, conversation_id)
            return

        if decision.action == "ask_clarification":
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Assistant] {decision.text}",
                reply_to_message_id=message.message_id,
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        if decision.action == "fallback":
            if self.can_parse_reminder(text):
                self.delegate_reminder_from_assistant(message, text, request_id, conversation_id)
                return

            if self.looks_like_weather_request(text):
                self.delegate_weather_from_assistant(message, text, request_id, conversation_id)
                return

        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Assistant] Принял запрос. Разберу его как личный помощник.",
            reply_to_message_id=message.message_id,
        )

        reply = self.assistant.respond(text, message.display_user)
        self.store.append(
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
            self.emit_agent_message(
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
            self.emit_agent_message(
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
                    "/python_pr <repo> <head> <base> <title> - открыть draft PR через Senior Python Developer\n"
                    "/python_file <repo> <ref> <path> - прочитать файл из GitHub\n"
                    "/python_change_file <repo> <base> <branch> <path> <task> - изменить файл через PR\n"
                    "/python_merge_pr <repo> <number> CONFIRM - смержить PR после прямого указания\n"
                    "/prompt_for_agent <role>: <task> - подготовить промпт для будущего агента\n\n"
                    "Примеры:\n"
                    "/weather Moscow\n"
                    "/remind через 10 минут проверить сборку\n"
                    "/python_dev спроектируй FastAPI endpoint для задач\n"
                    "/python_pr ckripto/telegram-aiteam feature-branch main Добавить GitHub skill\n"
                    "/python_file ckripto/telegram-aiteam main README.md\n"
                    "/remind завтра 09:30 написать план дня"
                ),
                reply_to_message_id=message.message_id,
            )
            return True

        if command == "/agents":
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=format_agents(),
                reply_to_message_id=message.message_id,
            )
            return True

        if command == "/status":
            tool_status = self.mcp.read_status()
            openai_status = "enabled" if self.config.openai_enabled else "offline fallback"
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    "[Assistant] Статус runtime:\n"
                    f"- chat_id: {message.chat_id}\n"
                    f"- OpenAI runtime: {openai_status}\n"
                    f"- Senior Python Developer runtime: {'enabled' if self.config.python_developer_enabled else 'offline fallback'}\n"
                    f"- GitHub capability: {'enabled' if self.config.github_enabled else 'not configured'}\n"
                    f"- event log: {self.store.count_events()} events\n"
                    f"- timezone: {self.config.local_timezone}\n"
                    f"- weather default: {self.config.weather_default_location}\n"
                    f"- MCP: {tool_status.summary}"
                ),
                reply_to_message_id=message.message_id,
            )
            return True

        if command == "/prompt_for_agent":
            return False

        if command == "/weather":
            self.delegate_weather_from_assistant(message, text, request_id, conversation_id)
            return True

        if command == "/remind":
            self.delegate_reminder_from_assistant(message, text, request_id, conversation_id)
            return True

        if command == "/reminders":
            self.handle_reminders_list(message, request_id, conversation_id)
            return True

        if command == "/python_dev":
            self.delegate_python_developer_from_assistant(message, text, request_id, conversation_id)
            return True

        if command == "/python_pr":
            self.handle_python_pull_request(message, text, request_id, conversation_id)
            return True

        if command == "/python_file":
            self.handle_python_file_read(message, text, request_id, conversation_id)
            return True

        if command == "/python_change_file":
            self.handle_python_file_change(message, text, request_id, conversation_id)
            return True

        if command == "/python_merge_pr":
            self.handle_python_merge_pr(message, text, request_id, conversation_id)
            return True

        return False

    def handle_python_file_read(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        parsed = self.parse_python_file_command(text)
        if parsed is None:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Assistant] Формат команды: /python_file <repo> <ref> <path>",
                reply_to_message_id=message.message_id,
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        repo, ref, path = parsed
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant -> Senior Python Developer] Прочитай файл {path} из {repo}@{ref}.",
            reply_to_message_id=message.message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        result = self.github.get_file(repo=repo, path=path, ref=ref)
        if not result.ok:
            text_result = f"[GitHub -> Senior Python Developer] Не удалось прочитать файл: {result.message}"
        else:
            content = result.content or ""
            preview = content[:3500]
            suffix = "\n... output truncated ..." if len(content) > len(preview) else ""
            text_result = f"[GitHub -> Senior Python Developer] {result.message}\n```text\n{preview}{suffix}\n```"
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=text_result,
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )

    def handle_python_file_change(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        parsed = self.parse_python_change_file_command(text)
        if parsed is None:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    "[Assistant] Формат команды:\n"
                    "/python_change_file <repo> <base> <branch> <path> <task>\n"
                    "Пример: /python_change_file ckripto/telegram-aiteam main codex/readme-update README.md Добавь раздел запуска"
                ),
                reply_to_message_id=message.message_id,
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        repo, base, branch, path, task = parsed
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant] Делегирую Senior Python Developer изменение {path} через PR.",
            reply_to_message_id=message.message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        file_result = self.github.get_file(repo=repo, path=path, ref=base)
        if not file_result.ok or file_result.content is None:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[GitHub -> Senior Python Developer] Не удалось прочитать исходный файл: {file_result.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return

        proposal = self.python_developer.propose_file_update(path=path, current_content=file_result.content, task=task)
        if not proposal.ok or proposal.content is None:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Senior Python Developer -> Assistant] Не смог подготовить изменение: {proposal.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return

        write_result = self.github.create_or_update_file_on_branch(
            repo=repo,
            base_branch=base,
            branch=branch,
            path=path,
            content=proposal.content,
            message=f"Update {path}",
        )
        if not write_result.ok:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[GitHub -> Senior Python Developer] Не удалось записать файл: {write_result.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return

        title = f"Update {path}"
        body = proposal.summary or f"Automated update for `{path}`.\n\nTask: {task}"
        pr_result = self.github.create_pull_request(repo=repo, head=branch, base=base, title=title, body=body, draft=True)
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Senior Python Developer -> Assistant] Изменил {path} в ветке {branch}.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        if pr_result.ok:
            final = f"[Assistant] PR с изменением открыт: {pr_result.url}"
        else:
            final = f"[Assistant] Файл изменён в ветке {branch}, но PR открыть не удалось: {pr_result.message}"
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=final,
            agent_id=PERSONAL_ASSISTANT_ID,
        )

    def handle_python_merge_pr(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        parsed = self.parse_python_merge_pr_command(text)
        if parsed is None:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Assistant] Для мержа нужно прямое указание: /python_merge_pr <repo> <number> CONFIRM",
                reply_to_message_id=message.message_id,
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        repo, number = parsed
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant -> GitHub] Получено прямое указание. Мержу PR #{number} в {repo}.",
            reply_to_message_id=message.message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        result = self.github.merge_pull_request(repo=repo, pull_number=number)
        final = (
            f"[GitHub -> Assistant] PR #{number} смержен. SHA: {result.sha}"
            if result.ok
            else f"[GitHub -> Assistant] Не удалось смержить PR #{number}: {result.message}"
        )
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=final,
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )

    def handle_python_pull_request(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        parsed = self.parse_python_pr_command(text)
        if parsed is None:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    "[Assistant] Формат команды:\n"
                    "/python_pr <repo> <head> <base> <title>\n"
                    "Пример: /python_pr ckripto/telegram-aiteam feature-branch main Добавить GitHub skill"
                ),
                reply_to_message_id=message.message_id,
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        repo, head, base, title = parsed
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Assistant] Делегирую Senior Python Developer подготовку PR description.",
            reply_to_message_id=message.message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        self.emit_delegation_event(
            from_agent_id=PERSONAL_ASSISTANT_ID,
            to_agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            task=f"Prepare GitHub PR body for {repo}: {title}",
            request_id=request_id,
            conversation_id=conversation_id,
            chat_id=message.chat_id,
        )
        developer_reply = self.python_developer.respond(
            "Prepare a concise GitHub pull request body in Markdown.\n"
            f"Repository: {repo}\n"
            f"Head branch: {head}\n"
            f"Base branch: {base}\n"
            f"Title: {title}\n"
            "Include summary, impact, and validation checklist."
        )
        pr_body = developer_reply.text
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Senior Python Developer -> Assistant] Подготовил PR body:\n{pr_body}",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant -> GitHub] Открываю draft PR в {repo}: {head} -> {base}.",
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        result = self.github.create_pull_request(
            repo=repo,
            head=head,
            base=base,
            title=title,
            body=pr_body,
            draft=True,
        )
        self.store.append(
            Event.create(
                event_type="tool_call_completed",
                actor_type="tool",
                actor_id="github.pr_open",
                visibility="public",
                payload={
                    "repo": repo,
                    "head": head,
                    "base": base,
                    "title": title,
                    "ok": result.ok,
                    "url": result.url,
                    "message": result.message,
                },
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=message.chat_id,
                target_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
        )
        if result.ok:
            text_result = f"[GitHub -> Assistant] {result.message}"
            final = f"[Assistant] PR открыт: {result.url}"
        else:
            text_result = f"[GitHub -> Assistant] Не удалось открыть PR: {result.message}"
            final = f"[Assistant] GitHub вернул ошибку при открытии PR: {result.message}"
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=text_result,
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=final,
            agent_id=PERSONAL_ASSISTANT_ID,
        )

    def delegate_python_developer_from_assistant(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        task = self.extract_command_payload(text, "/python_dev")
        self.delegate_python_developer_to_chat(
            chat_id=message.chat_id,
            text=task,
            request_id=request_id,
            conversation_id=conversation_id,
            reply_to_message_id=message.message_id,
        )

    def delegate_python_developer_to_chat(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
        reply_to_message_id: int | None = None,
        final_prefix: str = "[Assistant] Senior Python Developer вернул результат:",
    ) -> None:
        task = text.strip() or "Нужно уточнить задачу."
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Assistant] Делегирую задачу агенту Senior Python Developer.",
            reply_to_message_id=reply_to_message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        self.emit_delegation_event(
            from_agent_id=PERSONAL_ASSISTANT_ID,
            to_agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            task=task,
            request_id=request_id,
            conversation_id=conversation_id,
            chat_id=chat_id,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant -> Senior Python Developer] {task}",
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Senior Python Developer] Принял задачу. Подготовлю технический ответ.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        reply = self.python_developer.respond(task)
        self.store.append(
            Event.create(
                event_type="agent_run_completed",
                actor_type="agent",
                actor_id=SENIOR_PYTHON_DEVELOPER_ID,
                visibility="private",
                payload={"summary": reply.internal_summary},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=chat_id,
            )
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Senior Python Developer -> Assistant] {reply.text}",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"{final_prefix}\n{reply.text}",
            agent_id=PERSONAL_ASSISTANT_ID,
        )

    def delegate_weather_from_assistant(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.delegate_weather_to_chat(
            chat_id=message.chat_id,
            text=text,
            request_id=request_id,
            conversation_id=conversation_id,
            reply_to_message_id=message.message_id,
        )

    def delegate_weather_to_chat(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
        reply_to_message_id: int | None = None,
        final_prefix: str = "[Assistant] По данным Weather:",
    ) -> None:
        location = self.extract_weather_location(text)
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant] Вижу запрос про погоду. Делегирую его агенту Weather.",
            reply_to_message_id=reply_to_message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        self.emit_delegation_event(
            from_agent_id=PERSONAL_ASSISTANT_ID,
            to_agent_id=WEATHER_ASSISTANT_ID,
            task=f"Получить прогноз на сегодня для: {location}",
            request_id=request_id,
            conversation_id=conversation_id,
            chat_id=chat_id,
        )
        result = self.handle_weather(chat_id, text, request_id, conversation_id, delegated=True)
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"{final_prefix} {result}",
            agent_id=PERSONAL_ASSISTANT_ID,
        )

    def delegate_reminder_from_assistant(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Assistant] Это задача для планировщика. Делегирую её агенту Planner.",
            reply_to_message_id=message.message_id,
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        self.emit_delegation_event(
            from_agent_id=PERSONAL_ASSISTANT_ID,
            to_agent_id=PLANNER_ASSISTANT_ID,
            task=text,
            request_id=request_id,
            conversation_id=conversation_id,
            chat_id=message.chat_id,
        )
        result = self.handle_reminder(message, text, request_id, conversation_id, delegated=True)
        if result:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Assistant] Planner подтвердил: {result}",
                agent_id=PERSONAL_ASSISTANT_ID,
            )

    def handle_weather(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
        delegated: bool = False,
    ) -> str:
        location = self.extract_weather_location(text)
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=(
                f"[Assistant -> Weather] Получи прогноз на сегодня для: {location}."
                if delegated
                else f"[Weather] Проверю прогноз для: {location}."
            ),
            agent_id=PERSONAL_ASSISTANT_ID if delegated else WEATHER_ASSISTANT_ID,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Weather] Принял. Проверю прогноз для: {location}.",
            agent_id=WEATHER_ASSISTANT_ID,
        )
        self.store.append(
            Event.create(
                event_type="tool_call_requested",
                actor_type="agent",
                actor_id=WEATHER_ASSISTANT_ID,
                visibility="compact",
                payload={"capability": "weather.forecast", "location": location},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=chat_id,
            )
        )

        try:
            forecast = self.weather.forecast(location)
            self.store.append(
                Event.create(
                    event_type="tool_call_completed",
                    actor_type="tool",
                    actor_id="weather.forecast",
                    visibility="compact",
                    payload={"location": forecast.location_name, "summary": forecast.summary},
                    request_id=request_id,
                    conversation_id=conversation_id,
                    telegram_chat_id=chat_id,
                    target_id=WEATHER_ASSISTANT_ID,
                )
            )
            result = f"{forecast.location_name}: {forecast.summary}"
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    f"[Weather -> Assistant] {result}"
                    if delegated
                    else f"[Weather] {result}"
                ),
                agent_id=WEATHER_ASSISTANT_ID,
            )
            return result
        except Exception as exc:
            result = f"не получилось получить прогноз: {exc}"
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=(
                    f"[Weather -> Assistant] {result}"
                    if delegated
                    else f"[Weather] {result}"
                ),
                agent_id=WEATHER_ASSISTANT_ID,
            )
            return result

    def handle_reminder(
        self,
        message: TelegramMessage,
        text: str,
        request_id: str,
        conversation_id: str,
        delegated: bool = False,
    ) -> str | None:
        try:
            reminder = self.reminder_parser.parse(text)
        except ValueError as exc:
            self.emit_agent_message(
                chat_id=message.chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Planner] {exc}",
                reply_to_message_id=message.message_id,
                agent_id=PLANNER_ASSISTANT_ID,
            )
            return None

        reminder_id = new_id("rem")
        self.store.create_reminder(
            reminder_id=reminder_id,
            chat_id=message.chat_id,
            user_id=str(message.user_id) if message.user_id else None,
            text=reminder.text,
            due_at=reminder.due_at,
            created_at=utc_now(),
        )
        self.store.append(
            Event.create(
                event_type="tool_call_completed",
                actor_type="agent",
                actor_id=PLANNER_ASSISTANT_ID,
                visibility="public",
                payload={
                    "capability": "reminder.create",
                    "reminder_id": reminder_id,
                    "due_at": reminder.due_at,
                    "text": reminder.text,
                },
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=message.chat_id,
            )
        )
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=(
                ("[Planner -> Assistant] Готово, напомню.\n" if delegated else "[Planner] Готово, напомню.\n")
                + f"ID: {reminder_id}\n"
                f"Когда: {reminder.human_time}\n"
                f"Что: {reminder.text}"
            ),
            reply_to_message_id=message.message_id,
            agent_id=PLANNER_ASSISTANT_ID,
        )
        return f"создано напоминание {reminder_id} на {reminder.human_time}: {reminder.text}"

    def handle_reminders_list(
        self,
        message: TelegramMessage,
        request_id: str,
        conversation_id: str,
    ) -> None:
        reminders = self.store.pending_reminders(message.chat_id)
        if not reminders:
            text = "[Planner] В этой группе нет активных напоминаний."
        else:
            lines = ["[Planner] Ближайшие напоминания:"]
            for reminder in reminders:
                lines.append(f"- {reminder['id']} | {reminder['due_at']} | {reminder['text']}")
            text = "\n".join(lines)
        self.emit_agent_message(
            chat_id=message.chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=text,
            reply_to_message_id=message.message_id,
            agent_id=PLANNER_ASSISTANT_ID,
        )

    def process_due_reminders(self) -> None:
        now = datetime.now(self.timezone).isoformat()
        for reminder in self.store.due_reminders(now):
            request_id = new_id("req")
            conversation_id = f"tg_{reminder['chat_id']}"
            chat_id = int(reminder["chat_id"])
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Planner -> Assistant] Пора выполнить отложенную задачу: {reminder['text']}",
                agent_id=PLANNER_ASSISTANT_ID,
            )
            self.store.mark_reminder_sent(reminder["id"], utc_now())
            self.store.append(
                Event.create(
                    event_type="reminder_sent",
                    actor_type="agent",
                    actor_id=PLANNER_ASSISTANT_ID,
                    visibility="public",
                    payload={"reminder_id": reminder["id"], "text": reminder["text"]},
                    request_id=request_id,
                    conversation_id=conversation_id,
                    telegram_chat_id=chat_id,
                )
            )
            self.handle_deferred_intent(
                chat_id=chat_id,
                text=str(reminder["text"]),
                request_id=request_id,
                conversation_id=conversation_id,
            )

    def handle_deferred_intent(
        self,
        chat_id: int,
        text: str,
        request_id: str,
        conversation_id: str,
    ) -> None:
        decision = self.assistant.decide(text)
        should_delegate_weather = decision.action == "delegate_weather" or (
            decision.action == "fallback" and self.looks_like_weather_request(text)
        )
        if should_delegate_weather:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Assistant] Для отложенной задачи нужен Weather. Делегирую.",
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            self.delegate_weather_to_chat(
                chat_id=chat_id,
                text=text,
                request_id=request_id,
                conversation_id=conversation_id,
                final_prefix="[Assistant] Напоминаю, вы просили проверить это позже. По данным Weather:",
            )
            return

        if decision.action == "delegate_python_developer":
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Assistant] Для отложенной задачи нужен Senior Python Developer. Делегирую.",
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            self.delegate_python_developer_to_chat(
                chat_id=chat_id,
                text=decision.text,
                request_id=request_id,
                conversation_id=conversation_id,
                final_prefix="[Assistant] Напоминаю, вы просили выполнить это позже. Senior Python Developer вернул результат:",
            )
            return

        if decision.action == "ask_clarification":
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Assistant] По отложенной задаче нужно уточнение: {decision.text}",
                agent_id=PERSONAL_ASSISTANT_ID,
            )
            return

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant] Напоминаю: {decision.text if decision.action == 'answer' else text}",
            agent_id=PERSONAL_ASSISTANT_ID,
        )

    def extract_weather_location(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.lower().startswith("/weather"):
            parts = cleaned.split(maxsplit=1)
            location = parts[1].strip() if len(parts) > 1 else self.config.weather_default_location
            return self.normalize_location(location)

        lowered = cleaned.lower()
        for marker in (
            "прогноз погоды для ",
            "прогноз погоды в ",
            "погоду в ",
            "погоду для ",
            "погода в ",
            "погода для ",
            "прогноз в ",
            "weather in ",
        ):
            index = lowered.find(marker)
            if index >= 0:
                return self.normalize_location(cleaned[index + len(marker):].strip(" ?."))
        for prefix in ("погода ", "weather "):
            if lowered.startswith(prefix):
                return self.normalize_location(cleaned[len(prefix):].strip(" ?."))
        match = re.search(r"\bв\s+([A-Za-zА-Яа-яЁё -]+?)(?:[?.!,]|$)", cleaned)
        if match:
            return self.normalize_location(match.group(1).strip())
        return self.config.weather_default_location

    def normalize_location(self, location: str) -> str:
        value = location.strip(" ?.!,")
        aliases = {
            "питер": "Saint Petersburg",
            "питере": "Saint Petersburg",
            "спб": "Saint Petersburg",
            "санкт-петербург": "Saint Petersburg",
            "санкт-петербурга": "Saint Petersburg",
            "санкт-петербурге": "Saint Petersburg",
            "санкт петербург": "Saint Petersburg",
            "санкт петербурга": "Saint Petersburg",
            "санкт петербурге": "Saint Petersburg",
        }
        return aliases.get(value.lower(), value or self.config.weather_default_location)

    def looks_like_weather_request(self, text: str) -> bool:
        lowered = text.lower()
        return "погод" in lowered or lowered.startswith("weather ")

    def looks_like_reminder_request(self, text: str) -> bool:
        lowered = text.lower().strip()
        return lowered.startswith("напомни ") or lowered.startswith("напомнить ")

    def can_parse_reminder(self, text: str) -> bool:
        try:
            self.reminder_parser.parse(text)
        except ValueError:
            return False
        return True

    def extract_command_payload(self, text: str, command: str) -> str:
        stripped = text.strip()
        if stripped.lower().startswith(command):
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2:
                return parts[1].strip()
            return "Нужно уточнить задачу."
        return stripped

    def parse_python_pr_command(self, text: str) -> tuple[str, str, str, str] | None:
        parts = text.strip().split(maxsplit=4)
        if len(parts) < 5:
            return None
        _command, repo, head, base, title = parts
        if "/" not in repo or not head or not base or not title:
            return None
        return repo, head, base, title

    def parse_python_file_command(self, text: str) -> tuple[str, str, str] | None:
        parts = text.strip().split(maxsplit=3)
        if len(parts) != 4:
            return None
        _command, repo, ref, path = parts
        if "/" not in repo or not ref or not path:
            return None
        return repo, ref, path

    def parse_python_change_file_command(self, text: str) -> tuple[str, str, str, str, str] | None:
        parts = text.strip().split(maxsplit=5)
        if len(parts) != 6:
            return None
        _command, repo, base, branch, path, task = parts
        if "/" not in repo or not base or not branch or not path or not task:
            return None
        return repo, base, branch, path, task

    def parse_python_merge_pr_command(self, text: str) -> tuple[str, int] | None:
        parts = text.strip().split(maxsplit=3)
        if len(parts) != 4:
            return None
        _command, repo, number, confirmation = parts
        if "/" not in repo or confirmation != "CONFIRM":
            return None
        try:
            return repo, int(number)
        except ValueError:
            return None

    def emit_agent_message(
        self,
        chat_id: int,
        request_id: str,
        conversation_id: str,
        text: str,
        reply_to_message_id: int | None = None,
        agent_id: str = PERSONAL_ASSISTANT_ID,
    ) -> None:
        message_id = self.telegram.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
        )
        self.store.append(
            Event.create(
                event_type="agent_message",
                actor_type="agent",
                actor_id=agent_id,
                visibility="public",
                payload={"text": text},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=chat_id,
                telegram_message_id=message_id,
            )
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
        self.store.append(
            Event.create(
                event_type="agent_delegation_requested",
                actor_type="agent",
                actor_id=from_agent_id,
                target_id=to_agent_id,
                visibility="public",
                payload={"task": task},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=chat_id,
            )
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
