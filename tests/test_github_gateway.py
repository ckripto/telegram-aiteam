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


if __name__ == "__main__":
    unittest.main()

