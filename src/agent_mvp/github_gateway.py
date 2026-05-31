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


@dataclass(frozen=True)
class GitHubRepoResult:
    ok: bool
    message: str
    repo: str | None = None
    default_branch: str | None = None


@dataclass(frozen=True)
class GitHubTreeResult:
    ok: bool
    message: str
    files: tuple[str, ...] = ()


class GitHubGateway:
    def __init__(self, config: Config) -> None:
        self.config = config

    def get_file(self, repo: str, path: str, ref: str) -> GitHubFileResult:
        if not self.config.github_enabled:
            return GitHubFileResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        repo_result = self.resolve_repository(repo)
        if not repo_result.ok or not repo_result.repo:
            return GitHubFileResult(ok=False, message=repo_result.message)
        normalized_repo = repo_result.repo

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
        if not self.config.github_enabled:
            return GitHubWriteResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        repo_result = self.resolve_repository(repo)
        if not repo_result.ok or not repo_result.repo:
            return GitHubWriteResult(ok=False, message=repo_result.message)
        normalized_repo = repo_result.repo

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

    def get_repository(self, repo: str) -> GitHubRepoResult:
        if not self.config.github_enabled:
            return GitHubRepoResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        repo_result = self.resolve_repository(repo)
        if not repo_result.ok or not repo_result.repo:
            return repo_result
        normalized_repo = repo_result.repo

        result = self._request_json("GET", f"/repos/{normalized_repo}")
        if not result["ok"]:
            return GitHubRepoResult(ok=False, message=result["message"])
        default_branch = result["data"].get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            return GitHubRepoResult(ok=False, message=f"Repository has no default branch: {normalized_repo}")
        return GitHubRepoResult(
            ok=True,
            message=f"Repository default branch is {default_branch}.",
            repo=normalized_repo,
            default_branch=default_branch,
        )

    def resolve_repository(self, repo: str) -> GitHubRepoResult:
        normalized_repo = self._normalize_repo(repo)
        if not normalized_repo:
            return GitHubRepoResult(ok=False, message="Repository is required. Use owner/name or set GITHUB_DEFAULT_REPO.")
        if "/" in normalized_repo:
            return GitHubRepoResult(ok=True, message=f"Repository resolved: {normalized_repo}.", repo=normalized_repo)

        query = urllib.parse.quote(f"{normalized_repo} in:name")
        result = self._request_json("GET", f"/search/repositories?q={query}&per_page=10")
        if not result["ok"]:
            return GitHubRepoResult(ok=False, message=f"Cannot resolve repository {normalized_repo}: {result['message']}")
        matches = []
        for item in result["data"].get("items", []):
            if item.get("name") == normalized_repo and isinstance(item.get("full_name"), str):
                matches.append(item["full_name"])
        if len(matches) == 1:
            return GitHubRepoResult(ok=True, message=f"Repository resolved: {matches[0]}.", repo=matches[0])
        if len(matches) > 1:
            return GitHubRepoResult(
                ok=False,
                message=(
                    f"Repository name {normalized_repo} is ambiguous. "
                    f"Use one of: {', '.join(matches[:5])}."
                ),
            )
        return GitHubRepoResult(
            ok=False,
            message=f"Repository {normalized_repo} was not found. Set GITHUB_DEFAULT_REPO as owner/name.",
        )

    def list_files(self, repo: str, ref: str, max_files: int = 600) -> GitHubTreeResult:
        if not self.config.github_enabled:
            return GitHubTreeResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        repo_result = self.resolve_repository(repo)
        if not repo_result.ok or not repo_result.repo:
            return GitHubTreeResult(ok=False, message=repo_result.message)
        normalized_repo = repo_result.repo

        branch = self._request_json("GET", f"/repos/{normalized_repo}/git/ref/heads/{urllib.parse.quote(ref)}")
        if not branch["ok"]:
            return GitHubTreeResult(ok=False, message=f"Cannot read ref {ref}: {branch['message']}")
        commit_sha = branch["data"].get("object", {}).get("sha")
        if not commit_sha:
            return GitHubTreeResult(ok=False, message=f"Ref has no commit SHA: {ref}")

        commit = self._request_json("GET", f"/repos/{normalized_repo}/git/commits/{commit_sha}")
        if not commit["ok"]:
            return GitHubTreeResult(ok=False, message=f"Cannot read commit {commit_sha}: {commit['message']}")
        tree_sha = commit["data"].get("tree", {}).get("sha")
        if not tree_sha:
            return GitHubTreeResult(ok=False, message=f"Commit has no tree SHA: {commit_sha}")

        tree = self._request_json("GET", f"/repos/{normalized_repo}/git/trees/{tree_sha}?recursive=1")
        if not tree["ok"]:
            return GitHubTreeResult(ok=False, message=tree["message"])
        files: list[str] = []
        for item in tree["data"].get("tree", []):
            if item.get("type") != "blob":
                continue
            path = item.get("path")
            if isinstance(path, str):
                files.append(path)
            if len(files) >= max_files:
                break
        return GitHubTreeResult(
            ok=True,
            message=f"Read {len(files)} files from {normalized_repo}@{ref}.",
            files=tuple(files),
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
        if not self.config.github_enabled:
            return GitHubWriteResult(ok=False, message="GitHub capability is not configured. Set GITHUB_TOKEN in .env.")
        repo_result = self.resolve_repository(repo)
        if not repo_result.ok or not repo_result.repo:
            return GitHubWriteResult(ok=False, message=repo_result.message)
        normalized_repo = repo_result.repo

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

        repo_result = self.resolve_repository(repo)
        if not repo_result.ok or not repo_result.repo:
            return PullRequestResult(
                ok=False,
                message=repo_result.message,
            )
        normalized_repo = repo_result.repo

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
