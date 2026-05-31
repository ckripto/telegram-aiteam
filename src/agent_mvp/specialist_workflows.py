from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .agent_registry import (
    PERSONAL_ASSISTANT_ID,
    PLANNER_ASSISTANT_ID,
    SENIOR_PYTHON_DEVELOPER_ID,
    WEATHER_ASSISTANT_ID,
)
from .events import Event, new_id, utc_now
from .telegram import TelegramMessage


class SpecialistWorkflows:
    def __init__(self, app: Any, renderer: Any) -> None:
        self.app = app
        self.renderer = renderer

    @property
    def config(self) -> Any:
        return self.app.config

    @property
    def store(self) -> Any:
        return self.app.store

    @property
    def assistant(self) -> Any:
        return self.app.assistant

    @property
    def python_developer(self) -> Any:
        return self.app.python_developer

    @property
    def github(self) -> Any:
        return self.app.github

    @property
    def weather(self) -> Any:
        return self.app.weather

    @property
    def reminder_parser(self) -> Any:
        return self.app.reminder_parser

    @property
    def timezone(self) -> Any:
        return self.app.timezone

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
                text="[Assistant] Формат команды: /python_file [repo] <ref> <path>. Если repo не указан, нужен GITHUB_DEFAULT_REPO.",
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
                    "/python_change_file [repo] <base> <branch> <path> <task>\n"
                    "Пример: /python_change_file main codex/readme-update README.md Добавь раздел запуска\n"
                    "Если repo не указан, нужен GITHUB_DEFAULT_REPO."
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

        developer_task = self.add_developer_project_context(
            f"Repository: {repo}\nBase branch: {base}\nTarget branch: {branch}\nRequested change: {task}"
        )
        proposal = self.python_developer.propose_file_update(
            path=path,
            current_content=file_result.content,
            task=developer_task,
        )
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
                text="[Assistant] Для мержа нужно прямое указание: /python_merge_pr [repo] <number> CONFIRM. Если repo не указан, нужен GITHUB_DEFAULT_REPO.",
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
                    "/python_pr [repo] <head> <base> <title>\n"
                    "Пример: /python_pr feature-branch main Добавить GitHub skill\n"
                    "Если repo не указан, нужен GITHUB_DEFAULT_REPO."
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
        task_for_developer = self.add_developer_project_context(task)
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
            task=task_for_developer,
            request_id=request_id,
            conversation_id=conversation_id,
            chat_id=chat_id,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant -> Senior Python Developer] {task_for_developer}",
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text="[Senior Python Developer] Принял задачу. Подготовлю технический ответ.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        if self.try_handle_developer_pr_task(
            chat_id=chat_id,
            task=task_for_developer,
            user_task=task,
            request_id=request_id,
            conversation_id=conversation_id,
        ):
            return
        reply = self.python_developer.respond(task_for_developer)
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
            text="[Assistant] Вижу запрос про погоду. Делегирую его агенту Weather.",
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

    def add_developer_project_context(self, task: str) -> str:
        if not self.config.github_default_repo:
            return task
        return (
            "Default GitHub repository/current project: "
            f"{self.config.github_default_repo}.\n"
            "If the user does not name another repository explicitly, treat this repository "
            "as the current codebase, including the code that powers this agent workspace.\n\n"
            f"Task: {task}"
        )

    def should_open_pr_from_developer_task(self, task: str) -> bool:
        lowered = task.lower()
        has_pr_marker = bool(
            re.search(r"(?<![a-zа-я0-9])pr(?![a-zа-я0-9])", lowered)
            or re.search(r"(?<![a-zа-я0-9])пр(?![a-zа-я0-9])", lowered)
            or any(marker in lowered for marker in ("pull request", "пулл реквест", "пул-реквест", "пулл-реквест"))
        )
        action_markers = ("откры", "созда", "сдела", "подготов", "open", "create")
        return has_pr_marker and any(marker in lowered for marker in action_markers)

    def try_handle_developer_pr_task(
        self,
        chat_id: int,
        task: str,
        user_task: str,
        request_id: str,
        conversation_id: str,
    ) -> bool:
        if not self.should_open_pr_from_developer_task(user_task):
            return False

        repo = self.config.github_default_repo or ""
        if not repo:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Senior Python Developer -> Assistant] Не могу открыть PR: не настроен GITHUB_DEFAULT_REPO.",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True
        if not self.config.github_enabled:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Senior Python Developer -> Assistant] Не могу открыть PR: не настроен GITHUB_TOKEN.",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True
        if not self.config.python_developer_enabled:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text="[Senior Python Developer -> Assistant] Не могу подготовить изменения: не настроены PYTHON_DEVELOPER_API_KEY и PYTHON_DEVELOPER_MODEL.",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Senior Python Developer -> GitHub] Запрашиваю репозиторий по умолчанию: {repo}.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        repo_result = self.github.get_repository(repo)
        if not repo_result.ok or not repo_result.repo or not repo_result.default_branch:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[GitHub -> Senior Python Developer] Не удалось получить репозиторий: {repo_result.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True
        resolved_repo = repo_result.repo
        base = repo_result.default_branch

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[GitHub -> Senior Python Developer] Текущий проект: {resolved_repo}, base branch: {base}.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        tree_result = self.github.list_files(resolved_repo, base)
        if not tree_result.ok:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[GitHub -> Senior Python Developer] Не удалось прочитать дерево файлов: {tree_result.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Senior Python Developer] Изучу дерево проекта ({len(tree_result.files)} файлов) и выберу файлы для изменения.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        plan = self.python_developer.plan_repository_change(
            task=task,
            repo=resolved_repo,
            default_branch=base,
            files=tree_result.files,
        )
        if not plan.ok or not plan.title or not plan.branch or not plan.base or not plan.files:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Senior Python Developer -> Assistant] Не смог спланировать PR: {plan.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=(
                "[Senior Python Developer -> GitHub] Для PR прочитаю файлы:\n"
                + "\n".join(f"- {path}" for path in plan.files)
            ),
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        file_contents: dict[str, str] = {}
        for path in plan.files:
            file_result = self.github.get_file(resolved_repo, path, plan.base)
            if not file_result.ok or file_result.content is None:
                self.emit_agent_message(
                    chat_id=chat_id,
                    request_id=request_id,
                    conversation_id=conversation_id,
                    text=f"[GitHub -> Senior Python Developer] Не удалось прочитать {path}: {file_result.message}",
                    agent_id=SENIOR_PYTHON_DEVELOPER_ID,
                )
                return True
            file_contents[path] = file_result.content

        proposal = self.python_developer.propose_repository_file_updates(
            task=task,
            repo=resolved_repo,
            files=file_contents,
        )
        if not proposal.ok:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[Senior Python Developer -> Assistant] Не смог подготовить изменения: {proposal.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Senior Python Developer -> Assistant] Подготовил изменения для ветки {plan.branch}.",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        for update in proposal.updates:
            write_result = self.github.create_or_update_file_on_branch(
                repo=resolved_repo,
                base_branch=plan.base,
                branch=plan.branch,
                path=update.path,
                content=update.content,
                message=f"Update {update.path}",
            )
            if not write_result.ok:
                self.emit_agent_message(
                    chat_id=chat_id,
                    request_id=request_id,
                    conversation_id=conversation_id,
                    text=f"[GitHub -> Senior Python Developer] Не удалось записать {update.path}: {write_result.message}",
                    agent_id=SENIOR_PYTHON_DEVELOPER_ID,
                )
                return True

        body = proposal.summary or plan.summary or "Automated repository change."
        pr_result = self.github.create_pull_request(
            repo=resolved_repo,
            head=plan.branch,
            base=plan.base,
            title=plan.title,
            body=body,
            draft=True,
        )
        if not pr_result.ok:
            self.emit_agent_message(
                chat_id=chat_id,
                request_id=request_id,
                conversation_id=conversation_id,
                text=f"[GitHub -> Senior Python Developer] Изменения записаны, но PR открыть не удалось: {pr_result.message}",
                agent_id=SENIOR_PYTHON_DEVELOPER_ID,
            )
            return True

        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[GitHub -> Assistant] Pull request created: {pr_result.url}",
            agent_id=SENIOR_PYTHON_DEVELOPER_ID,
        )
        self.emit_agent_message(
            chat_id=chat_id,
            request_id=request_id,
            conversation_id=conversation_id,
            text=f"[Assistant] Senior Python Developer открыл draft PR: {pr_result.url}",
            agent_id=PERSONAL_ASSISTANT_ID,
        )
        return True

    def parse_python_pr_command(self, text: str) -> tuple[str, str, str, str] | None:
        full_parts = text.strip().split(maxsplit=4)
        if len(full_parts) >= 5 and "/" in full_parts[1]:
            _command, repo, head, base, title = full_parts
            if not head or not base or not title:
                return None
            return repo, head, base, title

        default_repo = self.config.github_default_repo
        default_parts = text.strip().split(maxsplit=3)
        if not default_repo or len(default_parts) != 4:
            return None
        _command, head, base, title = default_parts
        if not head or not base or not title:
            return None
        return default_repo, head, base, title

    def parse_python_file_command(self, text: str) -> tuple[str, str, str] | None:
        full_parts = text.strip().split(maxsplit=3)
        if len(full_parts) == 4 and "/" in full_parts[1]:
            _command, repo, ref, path = full_parts
            if not ref or not path:
                return None
            return repo, ref, path

        default_repo = self.config.github_default_repo
        default_parts = text.strip().split(maxsplit=2)
        if not default_repo or len(default_parts) != 3:
            return None
        _command, ref, path = default_parts
        if not ref or not path:
            return None
        return default_repo, ref, path

    def parse_python_change_file_command(self, text: str) -> tuple[str, str, str, str, str] | None:
        full_parts = text.strip().split(maxsplit=5)
        if len(full_parts) == 6 and "/" in full_parts[1]:
            _command, repo, base, branch, path, task = full_parts
            if not base or not branch or not path or not task:
                return None
            return repo, base, branch, path, task

        default_repo = self.config.github_default_repo
        default_parts = text.strip().split(maxsplit=4)
        if not default_repo or len(default_parts) != 5:
            return None
        _command, base, branch, path, task = default_parts
        if not base or not branch or not path or not task:
            return None
        return default_repo, base, branch, path, task

    def parse_python_merge_pr_command(self, text: str) -> tuple[str, int] | None:
        full_parts = text.strip().split(maxsplit=3)
        if len(full_parts) == 4 and "/" in full_parts[1]:
            _command, repo, number, confirmation = full_parts
            if confirmation != "CONFIRM":
                return None
            try:
                return repo, int(number)
            except ValueError:
                return None

        default_repo = self.config.github_default_repo
        default_parts = text.strip().split(maxsplit=2)
        if not default_repo or len(default_parts) != 3:
            return None
        _command, number, confirmation = default_parts
        if confirmation != "CONFIRM":
            return None
        try:
            return default_repo, int(number)
        except ValueError:
            return None
