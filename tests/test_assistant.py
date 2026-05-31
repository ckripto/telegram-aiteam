import unittest

from src.agent_mvp.assistant import AssistantRuntime
from src.agent_mvp.config import Config


class AssistantRuntimeTest(unittest.TestCase):
    def test_offline_prompt_for_agent(self) -> None:
        config = Config(
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
        runtime = AssistantRuntime(config)

        reply = runtime.respond("/prompt_for_agent QA: test payment retries", "@user")

        joined = "\n".join(reply.public_messages)
        self.assertIn("QA", joined)
        self.assertIn("test payment retries", joined)
        self.assertIn("Responsibilities", joined)


if __name__ == "__main__":
    unittest.main()
