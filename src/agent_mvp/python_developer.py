from __future__ import annotations

import json
import re
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


@dataclass(frozen=True)
class RepositoryChangePlan:
    ok: bool
    message: str
    title: str | None = None
    branch: str | None = None
    base: str | None = None
    files: tuple[str, ...] = ()
    summary: str | None = None


@dataclass(frozen=True)
class RepositoryFileUpdate:
    path: str
    content: str
    summary: str


@dataclass(frozen=True)
class RepositoryFileUpdateProposal:
    ok: bool
    message: str
    updates: tuple[RepositoryFileUpdate, ...] = ()
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

    def plan_repository_change(
        self,
        task: str,
        repo: str,
        default_branch: str,
        files: tuple[str, ...],
    ) -> RepositoryChangePlan:
        if not self.config.python_developer_enabled:
            return RepositoryChangePlan(
                ok=False,
                message="PYTHON_DEVELOPER_API_KEY and PYTHON_DEVELOPER_MODEL are required to plan repository changes.",
            )

        prompt = (
            "You are planning a small repository change that will be opened as a draft GitHub PR.\n"
            "Return JSON only with keys: `title`, `branch`, `base`, `files`, and `summary`.\n"
            "`files` must contain 1-6 existing paths from the repository tree below that should be edited.\n"
            "`branch` must be a short safe branch name using letters, numbers, dashes, slashes, or underscores.\n"
            "Do not ask for a repository link; the repository below is the current project.\n\n"
            f"Repository: {repo}\n"
            f"Default base branch: {default_branch}\n"
            f"Task: {task}\n\n"
            "Repository files:\n"
            "```text\n"
            f"{chr(10).join(files[:600])}\n"
            "```"
        )
        reply = self._respond_with_model(prompt)
        try:
            parsed = json.loads(reply.text)
        except json.JSONDecodeError:
            return RepositoryChangePlan(ok=False, message="Model did not return valid JSON for repository plan.")

        title = parsed.get("title")
        branch = parsed.get("branch")
        base = parsed.get("base") or default_branch
        selected_files = parsed.get("files")
        summary = parsed.get("summary")
        if not isinstance(title, str) or not title.strip():
            return RepositoryChangePlan(ok=False, message="Repository plan did not include a non-empty `title`.")
        if not isinstance(branch, str) or not branch.strip():
            return RepositoryChangePlan(ok=False, message="Repository plan did not include a non-empty `branch`.")
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", branch.strip()):
            return RepositoryChangePlan(ok=False, message="Repository plan returned an unsafe branch name.")
        if not isinstance(base, str) or not base.strip():
            return RepositoryChangePlan(ok=False, message="Repository plan did not include a non-empty `base`.")
        if not isinstance(selected_files, list):
            return RepositoryChangePlan(ok=False, message="Repository plan did not include `files`.")

        known_files = set(files)
        normalized_files: list[str] = []
        for path in selected_files:
            if isinstance(path, str) and path in known_files and path not in normalized_files:
                normalized_files.append(path)
        if not normalized_files:
            return RepositoryChangePlan(ok=False, message="Repository plan did not select existing files.")
        if not isinstance(summary, str):
            summary = "Automated repository change."
        return RepositoryChangePlan(
            ok=True,
            message="Prepared repository change plan.",
            title=title.strip(),
            branch=branch.strip(),
            base=base.strip(),
            files=tuple(normalized_files[:6]),
            summary=summary.strip(),
        )

    def propose_repository_file_updates(
        self,
        task: str,
        repo: str,
        files: dict[str, str],
    ) -> RepositoryFileUpdateProposal:
        if not self.config.python_developer_enabled:
            return RepositoryFileUpdateProposal(
                ok=False,
                message="PYTHON_DEVELOPER_API_KEY and PYTHON_DEVELOPER_MODEL are required to generate repository changes.",
            )

        file_blocks = []
        for path, content in files.items():
            file_blocks.append(f"Path: {path}\n```text\n{content}\n```")
        prompt = (
            "You are editing repository files for a draft GitHub PR.\n"
            "Return JSON only with keys `updates` and `summary`.\n"
            "`updates` must be an array of objects with keys `path`, `content`, and `summary`.\n"
            "`content` must be the complete replacement content for that file, not a patch.\n"
            "Only include files that need changes; paths must match the provided files exactly.\n\n"
            f"Repository: {repo}\n"
            f"Task: {task}\n\n"
            "Files:\n"
            f"{chr(10).join(file_blocks)}"
        )
        reply = self._respond_with_model(prompt)
        try:
            parsed = json.loads(reply.text)
        except json.JSONDecodeError:
            return RepositoryFileUpdateProposal(ok=False, message="Model did not return valid JSON for repository updates.")

        raw_updates = parsed.get("updates")
        summary = parsed.get("summary")
        if not isinstance(raw_updates, list):
            return RepositoryFileUpdateProposal(ok=False, message="Repository update response did not include `updates`.")
        allowed_paths = set(files)
        updates: list[RepositoryFileUpdate] = []
        for item in raw_updates:
            if not isinstance(item, dict):
                continue
            path = item.get("path")
            content = item.get("content")
            item_summary = item.get("summary")
            if not isinstance(path, str) or path not in allowed_paths:
                continue
            if not isinstance(content, str) or not content:
                continue
            if not isinstance(item_summary, str):
                item_summary = f"Updated {path}."
            updates.append(RepositoryFileUpdate(path=path, content=content, summary=item_summary))
        if not updates:
            return RepositoryFileUpdateProposal(ok=False, message="Repository update response did not include valid file updates.")
        if not isinstance(summary, str):
            summary = "\n".join(f"- {update.summary}" for update in updates)
        return RepositoryFileUpdateProposal(
            ok=True,
            message="Prepared repository file updates.",
            updates=tuple(updates),
            summary=summary,
        )

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
