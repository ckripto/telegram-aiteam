import unittest

from src.agent_mvp.agent_registry import SENIOR_PYTHON_DEVELOPER_ID, format_assistant_agent_context
from src.agent_mvp.config import Config
from src.agent_mvp.python_developer import SeniorPythonDeveloperRuntime


class SeniorPythonDeveloperTest(unittest.TestCase):
    def test_agent_is_visible_to_assistant_context(self) -> None:
        context = format_assistant_agent_context()

        self.assertIn(SENIOR_PYTHON_DEVELOPER_ID, context)
        self.assertIn("PYTHON_DEVELOPER_MODEL", context)
        self.assertIn("python.code_review", context)

    def test_offline_fallback_uses_own_credentials(self) -> None:
        runtime = SeniorPythonDeveloperRuntime(
            Config(
                telegram_bot_token="test",
                telegram_allowed_chat_id=None,
                openai_api_key=None,
                openai_model=None,
                python_developer_api_key=None,
                python_developer_model=None,
                python_developer_base_url="https://api.openai.com/v1",
                database_path=":memory:",
                poll_timeout_seconds=1,
                poll_interval_seconds=1,
                public_tool_events=True,
                local_timezone="Europe/Moscow",
                weather_default_location="Moscow",
            )
        )

        reply = runtime.respond("Review this Python function")

        self.assertIn("PYTHON_DEVELOPER_API_KEY", reply.text)
        self.assertIn("PYTHON_DEVELOPER_MODEL", reply.text)


if __name__ == "__main__":
    unittest.main()

