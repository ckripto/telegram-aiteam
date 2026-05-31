from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Config


@dataclass(frozen=True)
class PullRequestResult:
    ok: bool
    message: str
    url: str | None = None


class GitHubGateway:
    def __init__(self, config: Config) -> None:
        self.config = config

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

        normalized_repo = repo or self.config.github_default_repo
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
        endpoint = f"{self.config.github_api_base_url.rstrip('/')}/repos/{normalized_repo}/pulls"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.github_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "telegram-agent-workspace",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            return PullRequestResult(
                ok=False,
                message=f"GitHub API error {exc.code}: {error_body[:900]}",
            )
        except OSError as exc:
            return PullRequestResult(
                ok=False,
                message=f"GitHub connection error: {exc}",
            )

        url = data.get("html_url")
        return PullRequestResult(
            ok=True,
            message=f"Pull request created: {url}",
            url=url,
        )

