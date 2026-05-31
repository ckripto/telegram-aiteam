from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Config


SYSTEM_PROMPT = """\
You are Senior Python Developer, a specialist agent inside a Telegram-visible multi-agent workspace.

Responsibilities:
- design Python backend implementations;
- review Python code and architecture;
- debug Python issues;
- explain tradeoffs clearly;
- produce practical implementation guidance.

Interaction rules:
- answer in the same language as the user unless asked otherwise;
- be concise enough for Telegram;
- include assumptions and risks when relevant;
- do not claim repository or tool access unless provided in the task context;
- if a task context includes a default GitHub repository, treat it as the current project codebase,
  including the code that powers this agent workspace;
- return your result to Assistant, because Assistant is the user-facing coordinator.
"""


@dataclass(frozen=True)
class PythonDeveloperReply:
    text: str
    internal_summary: str


@dataclass(frozen=True)
class FileUpdateProposal:
    ok: bool
    message: str
    content: str | None = None
    summary: str | None = None


class SeniorPythonDeveloperRuntime:
    def __init__(self, config: Config) -> None:
        self.config = config

    def respond(self, task: str) -> PythonDeveloperReply:
        if not self.config.python_developer_enabled:
            return PythonDeveloperReply(
                text=(
                    "Я готов принять Python-задачу, но для моего отдельного runtime не настроены "
                    "PYTHON_DEVELOPER_API_KEY и PYTHON_DEVELOPER_MODEL."
                ),
                internal_summary="Senior Python Developer offline fallback.",
            )
        return self._respond_with_model(task)

    def propose_file_update(self, path: str, current_content: str, task: str) -> FileUpdateProposal:
        if not self.config.python_developer_enabled:
            return FileUpdateProposal(
                ok=False,
                message="PYTHON_DEVELOPER_API_KEY and PYTHON_DEVELOPER_MODEL are required to generate file changes.",
            )

        prompt = (
            "You are editing a repository file. Return JSON only with keys `content` and `summary`.\n"
            "`content` must be the complete replacement file content, not a patch.\n"
            "`summary` must explain the change in 1-3 short bullet points.\n\n"
            f"Path: {path}\n"
            f"Task: {task}\n\n"
            "Current file content:\n"
            "```text\n"
            f"{current_content}\n"
            "```"
        )
        reply = self._respond_with_model(prompt)
        try:
            parsed = json.loads(reply.text)
        except json.JSONDecodeError:
            return FileUpdateProposal(ok=False, message="Model did not return valid JSON for file update.")

        content = parsed.get("content")
        summary = parsed.get("summary")
        if not isinstance(content, str) or not content:
            return FileUpdateProposal(ok=False, message="Model response did not include non-empty `content`.")
        if not isinstance(summary, str):
            summary = "Automated file update."
        return FileUpdateProposal(ok=True, message="Prepared file update.", content=content, summary=summary)

    def _respond_with_model(self, task: str) -> PythonDeveloperReply:
        assert self.config.python_developer_api_key is not None
        assert self.config.python_developer_model is not None

        payload = {
            "model": self.config.python_developer_model,
            "input": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ],
        }
        endpoint = self.config.python_developer_base_url.rstrip("/") + "/responses"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.python_developer_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return PythonDeveloperReply(
                text=f"Не смог обратиться к моей модели. Ошибка API: {error_body[:900]}",
                internal_summary=f"Python developer model HTTP error {exc.code}",
            )
        except OSError as exc:
            return PythonDeveloperReply(
                text=f"Не смог подключиться к моей модели: {exc}",
                internal_summary=f"Python developer model connection error: {exc}",
            )

        text = self._extract_response_text(data)
        if not text:
            text = "Моя модель вернула пустой ответ. Можно повторить задачу."
        return PythonDeveloperReply(
            text=text,
            internal_summary="Answered through Senior Python Developer model.",
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
