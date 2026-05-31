import unittest

from src.agent_mvp.config import Config
from src.agent_mvp.github_gateway import GitHubGateway


class GitHubGatewayTest(unittest.TestCase):
    def test_create_pr_requires_token(self) -> None:
        gateway = GitHubGateway(
            Config(
                telegram_bot_token="test",
                telegram_allowed_chat_id=None,
                openai_api_key=None,
                openai_model=None,
                python_developer_api_key=None,
                python_developer_model=None,
                python_developer_base_url="https://api.openai.com/v1",
                github_token=None,
                github_default_repo=None,
                github_api_base_url="https://api.github.com",
                database_path=":memory:",
                poll_timeout_seconds=1,
                poll_interval_seconds=1,
                public_tool_events=True,
                local_timezone="Europe/Moscow",
                weather_default_location="Moscow",
            )
        )

        result = gateway.create_pull_request(
            repo="ckripto/telegram-aiteam",
            head="feature",
            base="main",
            title="Test PR",
            body="Body",
        )

        self.assertFalse(result.ok)
        self.assertIn("GITHUB_TOKEN", result.message)

    def test_read_file_requires_token(self) -> None:
        gateway = GitHubGateway(
            Config(
                telegram_bot_token="test",
                telegram_allowed_chat_id=None,
                openai_api_key=None,
                openai_model=None,
                python_developer_api_key=None,
                python_developer_model=None,
                python_developer_base_url="https://api.openai.com/v1",
                github_token=None,
                github_default_repo=None,
                github_api_base_url="https://api.github.com",
                database_path=":memory:",
                poll_timeout_seconds=1,
                poll_interval_seconds=1,
                public_tool_events=True,
                local_timezone="Europe/Moscow",
                weather_default_location="Moscow",
            )
        )

        result = gateway.get_file(repo="ckripto/telegram-aiteam", path="README.md", ref="main")

        self.assertFalse(result.ok)
        self.assertIn("GITHUB_TOKEN", result.message)

    def test_resolves_short_default_repo_name(self) -> None:
        gateway = GitHubGateway(
            Config(
                telegram_bot_token="test",
                telegram_allowed_chat_id=None,
                openai_api_key=None,
                openai_model=None,
                python_developer_api_key=None,
                python_developer_model=None,
                python_developer_base_url="https://api.openai.com/v1",
                github_token="token",
                github_default_repo="telegram-aiteam",
                github_api_base_url="https://api.github.com",
                database_path=":memory:",
                poll_timeout_seconds=1,
                poll_interval_seconds=1,
                public_tool_events=True,
                local_timezone="Europe/Moscow",
                weather_default_location="Moscow",
            )
        )

        def fake_request(method: str, path: str, payload: dict | None = None) -> dict:
            self.assertEqual(method, "GET")
            self.assertIn("/search/repositories", path)
            return {
                "ok": True,
                "data": {
                    "items": [
                        {"name": "telegram-aiteam", "full_name": "ckripto/telegram-aiteam"},
                    ]
                },
            }

        gateway._request_json = fake_request  # type: ignore[method-assign]

        result = gateway.resolve_repository("")

        self.assertTrue(result.ok)
        self.assertEqual(result.repo, "ckripto/telegram-aiteam")


if __name__ == "__main__":
    unittest.main()
