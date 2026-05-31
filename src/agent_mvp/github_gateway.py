from __future__ import annotations

import json
import base64
import urllib.parse
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True)
class PullRequestResult:
    ok: bool
    message: str
    url: str | None = None


@dataclass(frozen=True)
class GitHubFileResult:
    ok: bool
    message: str
    path: str | None = None
    content: str | None = None
    sha: str | None = None
    url: str | None = None


@dataclass(frozen=True)
class GitHubWriteResult:
    ok: bool
    message: str
    url: str | None = None
    sha: str | None = None


class GitHubGateway:
    def __init__(self, config: Config) -> None:
        self.config = config

    def get_file(self, repo: str, path: str, ref: str) -> GitHubFileResult:
        normalized_repo = self._normalize_repo(repo)
        if not self.config.github_enabled:
            return GitHubFileResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        if not normalized_repo:
            return GitHubFileResult(ok=False, message="Repository is required. Use owner/name or set GITHUB_DEFAULT_REPO.")

        quoted_path = "/".join(urllib.parse.quote(part) for part in path.split("/"))
        result = self._request_json(
            "GET",
            f"/repos/{normalized_repo}/contents/{quoted_path}?ref={urllib.parse.quote(ref)}",
        )
        if not result["ok"]:
            return GitHubFileResult(ok=False, message=result["message"])

        data = result["data"]
        if data.get("type") != "file":
            return GitHubFileResult(ok=False, message=f"Path is not a file: {path}")
        encoded = str(data.get("content", ""))
        content = base64.b64decode(encoded).decode("utf-8")
        return GitHubFileResult(
            ok=True,
            message=f"Read {path} from {normalized_repo}@{ref}.",
            path=path,
            content=content,
            sha=data.get("sha"),
            url=data.get("html_url"),
        )

    def create_or_update_file_on_branch(
        self,
        repo: str,
        base_branch: str,
        branch: str,
        path: str,
        content: str,
        message: str,
    ) -> GitHubWriteResult:
        normalized_repo = self._normalize_repo(repo)
        if not self.config.github_enabled:
            return GitHubWriteResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        if not normalized_repo:
            return GitHubWriteResult(ok=False, message="Repository is required. Use owner/name or set GITHUB_DEFAULT_REPO.")

        branch_result = self.ensure_branch(normalized_repo, branch, base_branch)
        if not branch_result.ok:
            return branch_result

        existing = self.get_file(normalized_repo, path, branch)
        sha = existing.sha if existing.ok else None
        quoted_path = "/".join(urllib.parse.quote(part) for part in path.split("/"))
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        if sha:
            payload["sha"] = sha

        result = self._request_json("PUT", f"/repos/{normalized_repo}/contents/{quoted_path}", payload)
        if not result["ok"]:
            return GitHubWriteResult(ok=False, message=result["message"])
        data = result["data"]
        commit = data.get("commit", {})
        content_info = data.get("content", {})
        return GitHubWriteResult(
            ok=True,
            message=f"Updated {path} on {branch}.",
            url=content_info.get("html_url"),
            sha=commit.get("sha"),
        )

    def ensure_branch(self, repo: str, branch: str, base_branch: str) -> GitHubWriteResult:
        existing = self._request_json("GET", f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(branch)}")
        if existing["ok"]:
            sha = existing["data"].get("object", {}).get("sha")
            return GitHubWriteResult(ok=True, message=f"Branch exists: {branch}", sha=sha)

        base = self._request_json("GET", f"/repos/{repo}/git/ref/heads/{urllib.parse.quote(base_branch)}")
        if not base["ok"]:
            return GitHubWriteResult(ok=False, message=f"Cannot read base branch {base_branch}: {base['message']}")
        base_sha = base["data"].get("object", {}).get("sha")
        if not base_sha:
            return GitHubWriteResult(ok=False, message=f"Base branch has no SHA: {base_branch}")

        created = self._request_json(
            "POST",
            f"/repos/{repo}/git/refs",
            {"ref": f"refs/heads/{branch}", "sha": base_sha},
        )
        if not created["ok"]:
            return GitHubWriteResult(ok=False, message=created["message"])
        return GitHubWriteResult(ok=True, message=f"Created branch {branch} from {base_branch}.", sha=base_sha)

    def merge_pull_request(
        self,
        repo: str,
        pull_number: int,
        merge_method: str = "squash",
    ) -> GitHubWriteResult:
        normalized_repo = self._normalize_repo(repo)
        if not self.config.github_enabled:
            return GitHubWriteResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        if not normalized_repo:
            return GitHubWriteResult(ok=False, message="Repository is required. Use owner/name or set GITHUB_DEFAULT_REPO.")

        result = self._request_json(
            "PUT",
            f"/repos/{normalized_repo}/pulls/{pull_number}/merge",
            {"merge_method": merge_method},
        )
        if not result["ok"]:
            return GitHubWriteResult(ok=False, message=result["message"])
        data = result["data"]
        return GitHubWriteResult(
            ok=bool(data.get("merged")),
            message=str(data.get("message", "Merge completed.")),
            sha=data.get("sha"),
        )

    def create_pull_request(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = True,
    ) -> PullRequestResult:
        if not self.config.github_enabled:
            return PullRequestResult(
                ok=False,
                message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.",
            )

        normalized_repo = self._normalize_repo(repo)
        if not normalized_repo:
            return PullRequestResult(
                ok=False,
                message="Repository is required. Use owner/name or set GITHUB_DEFAULT_REPO.",
            )

        payload = {
            "title": title,
            "head": head,
            "base": base,
            "body": body,
            "draft": draft,
        }
        result = self._request_json("POST", f"/repos/{normalized_repo}/pulls", payload)
        if not result["ok"]:
            return PullRequestResult(ok=False, message=result["message"])

        data = result["data"]
        url = data.get("html_url")
        return PullRequestResult(
            ok=True,
            message=f"Pull request created: {url}",
            url=url,
        )

    def _normalize_repo(self, repo: str) -> str | None:
        return repo or self.config.github_default_repo

    def _request_json(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = None
        headers = {
            "Authorization": f"Bearer {self.config.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "telegram-agent-workspace",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        endpoint = f"{self.config.github_api_base_url.rstrip('/')}{path}"
        request = urllib.request.Request(endpoint, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
            return {"ok": True, "data": json.loads(body) if body else {}}
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return {"ok": False, "message": f"GitHub API error {exc.code}: {error_body[:900]}"}
        except OSError as exc:
            return {"ok": False, "message": f"GitHub connection error: {exc}"}
