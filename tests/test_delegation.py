import tempfile
import unittest

from src.agent_mvp.agent_registry import (
    PLANNER_ASSISTANT_ID,
    WEATHER_ASSISTANT_ID,
    format_assistant_agent_context,
)
from src.agent_mvp.app import AgentMvpApp
from src.agent_mvp.config import Config
from src.agent_mvp.github_gateway import GitHubFileResult, GitHubRepoResult, GitHubTreeResult, GitHubWriteResult, PullRequestResult
from src.agent_mvp.python_developer import RepositoryChangePlan, RepositoryFileUpdate, RepositoryFileUpdateProposal
from src.agent_mvp.telegram import TelegramMessage
from src.agent_mvp.weather import WeatherForecast


def test_config(database_path: str, github_default_repo: str | None = None) -> Config:
    return Config(
        telegram_bot_token="test",
        telegram_allowed_chat_id=None,
        openai_api_key=None,
        openai_model=None,
        python_developer_api_key=None,
        python_developer_model=None,
        python_developer_base_url="https://api.openai.com/v1",
        github_token=None,
        github_default_repo=github_default_repo,
        github_api_base_url="https://api.github.com",
        database_path=database_path,
        poll_timeout_seconds=1,
        poll_interval_seconds=1,
        public_tool_events=True,
        local_timezone="Europe/Moscow",
        weather_default_location="Moscow",
    )


class DelegationTest(unittest.TestCase):
    def test_assistant_context_includes_specialist_agents(self) -> None:
        context = format_assistant_agent_context()

        self.assertIn(WEATHER_ASSISTANT_ID, context)
        self.assertIn(PLANNER_ASSISTANT_ID, context)
        self.assertIn("weather.forecast", context)
        self.assertIn("reminder.create", context)

    def test_extracts_piter_weather_location(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name))

            location = app.extract_weather_location("Подскажи мне погоду на сегодня в Питере")

            self.assertEqual(location, "Saint Petersburg")

    def test_weather_router_detects_accusative_form(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name))

            self.assertTrue(app.looks_like_weather_request("Подскажи мне погоду на сегодня в Питере"))

    def test_normalizes_saint_petersburg_genitive(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name))

            location = app.extract_weather_location("Нужен прогноз погоды для Санкт-Петербурга")

            self.assertEqual(location, "Saint Petersburg")

    def test_delayed_weather_request_goes_to_planner_first(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name))
            telegram = FakeTelegram()
            weather = FakeWeather()
            app.telegram = telegram
            app.weather = weather

            app.handle_message(
                TelegramMessage(
                    update_id=1,
                    chat_id=100,
                    message_id=10,
                    text="Через 3 минуты проверь погоду в Питере",
                    user_id=42,
                    username="user",
                    first_name=None,
                )
            )

            joined = "\n".join(telegram.messages)
            self.assertIn("[Assistant] Это задача для планировщика", joined)
            self.assertIn("[Planner -> Assistant] Готово, напомню.", joined)
            self.assertNotIn("[Assistant -> Weather]", joined)
            self.assertEqual(weather.calls, [])

    def test_due_deferred_weather_intent_returns_to_assistant_then_weather(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name))
            telegram = FakeTelegram()
            weather = FakeWeather()
            app.telegram = telegram
            app.weather = weather
            app.store.create_reminder(
                reminder_id="rem_due",
                chat_id=100,
                user_id="42",
                text="проверь погоду в Питере",
                due_at="2000-01-01T12:00:00+03:00",
                created_at="2000-01-01T11:59:00+03:00",
            )

            app.process_due_reminders()

            joined = "\n".join(telegram.messages)
            self.assertIn("[Planner -> Assistant] Пора выполнить отложенную задачу", joined)
            self.assertIn("[Assistant] Для отложенной задачи нужен Weather", joined)
            self.assertIn("[Assistant -> Weather] Получи прогноз", joined)
            self.assertIn("[Weather -> Assistant]", joined)
            self.assertIn("[Assistant] Напоминаю", joined)
            self.assertEqual(weather.calls, ["Saint Petersburg"])

    def test_python_github_commands_use_default_repo_when_omitted(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name, github_default_repo="ckripto/telegram-aiteam"))

            self.assertEqual(
                app.parse_python_file_command("/python_file main README.md"),
                ("ckripto/telegram-aiteam", "main", "README.md"),
            )
            self.assertEqual(
                app.parse_python_pr_command("/python_pr feature main Add GitHub skill"),
                ("ckripto/telegram-aiteam", "feature", "main", "Add GitHub skill"),
            )
            self.assertEqual(
                app.parse_python_change_file_command(
                    "/python_change_file main codex/readme-update README.md Add setup instructions"
                ),
                (
                    "ckripto/telegram-aiteam",
                    "main",
                    "codex/readme-update",
                    "README.md",
                    "Add setup instructions",
                ),
            )
            self.assertEqual(
                app.parse_python_merge_pr_command("/python_merge_pr 12 CONFIRM"),
                ("ckripto/telegram-aiteam", 12),
            )

    def test_python_github_commands_still_accept_explicit_repo(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name, github_default_repo="ckripto/telegram-aiteam"))

            self.assertEqual(
                app.parse_python_file_command("/python_file other/project main README.md"),
                ("other/project", "main", "README.md"),
            )

    def test_python_github_commands_require_default_repo_when_omitted(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name))

            self.assertIsNone(app.parse_python_file_command("/python_file main README.md"))

    def test_python_developer_task_includes_default_repo_context(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            app = AgentMvpApp(test_config(tmp.name, github_default_repo="ckripto/telegram-aiteam"))

            task = app.add_developer_project_context("Посмотри текущий код")

            self.assertIn("ckripto/telegram-aiteam", task)
            self.assertIn("current codebase", task)

    def test_python_developer_pr_task_opens_pr_through_github_workflow(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            config = test_config(tmp.name, github_default_repo="telegram-aiteam")
            config = Config(
                **{
                    **config.__dict__,
                    "github_token": "token",
                    "python_developer_api_key": "developer-token",
                    "python_developer_model": "developer-model",
                }
            )
            app = AgentMvpApp(config)
            telegram = FakeTelegram()
            app.telegram = telegram
            app.github = FakeGitHub()
            app.python_developer = FakePythonDeveloper()

            app.delegate_python_developer_to_chat(
                chat_id=100,
                text="Добавить фитчу: сообщения должны быть размечены в markdown. Открыть PR в репозиторий.",
                request_id="req",
                conversation_id="conv",
            )

            joined = "\n".join(telegram.messages)
            self.assertIn("[Senior Python Developer -> GitHub] Запрашиваю репозиторий по умолчанию: telegram-aiteam.", joined)
            self.assertIn("[GitHub -> Senior Python Developer] Текущий проект: ckripto/telegram-aiteam", joined)
            self.assertIn("[GitHub -> Assistant] Pull request created: https://github.com/ckripto/telegram-aiteam/pull/7", joined)
            self.assertIn("[Assistant] Senior Python Developer открыл draft PR", joined)


class FakeTelegram:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> int:
        self.messages.append(text)
        return len(self.messages)


class FakeWeather:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def forecast(self, location: str) -> WeatherForecast:
        self.calls.append(location)
        return WeatherForecast(
            location_name="Saint Petersburg",
            current_temperature=10,
            current_wind_speed=5,
            daily_min=8,
            daily_max=12,
            precipitation_probability=20,
            summary="Сейчас 10°C, ветер 5 км/ч. Сегодня ожидается от 8°C до 12°C, вероятность осадков до 20%.",
        )


class FakeGitHub:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str]] = []

    def get_repository(self, repo: str) -> GitHubRepoResult:
        return GitHubRepoResult(
            ok=True,
            message="ok",
            repo="ckripto/telegram-aiteam",
            default_branch="main",
        )

    def list_files(self, repo: str, ref: str) -> GitHubTreeResult:
        return GitHubTreeResult(ok=True, message="ok", files=("src/agent_mvp/telegram.py", "README.md"))

    def get_file(self, repo: str, path: str, ref: str) -> GitHubFileResult:
        return GitHubFileResult(ok=True, message="ok", path=path, content="old", sha="sha")

    def create_or_update_file_on_branch(
        self,
        repo: str,
        base_branch: str,
        branch: str,
        path: str,
        content: str,
        message: str,
    ) -> GitHubWriteResult:
        self.writes.append((path, content))
        return GitHubWriteResult(ok=True, message="updated")

    def create_pull_request(
        self,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str,
        draft: bool = True,
    ) -> PullRequestResult:
        return PullRequestResult(
            ok=True,
            message="Pull request created: https://github.com/ckripto/telegram-aiteam/pull/7",
            url="https://github.com/ckripto/telegram-aiteam/pull/7",
        )


class FakePythonDeveloper:
    def plan_repository_change(
        self,
        task: str,
        repo: str,
        default_branch: str,
        files: tuple[str, ...],
    ) -> RepositoryChangePlan:
        return RepositoryChangePlan(
            ok=True,
            message="ok",
            title="Add Markdown Telegram messages",
            branch="codex/telegram-markdown",
            base="main",
            files=("src/agent_mvp/telegram.py",),
            summary="Plan",
        )

    def propose_repository_file_updates(
        self,
        task: str,
        repo: str,
        files: dict[str, str],
    ) -> RepositoryFileUpdateProposal:
        return RepositoryFileUpdateProposal(
            ok=True,
            message="ok",
            updates=(
                RepositoryFileUpdate(
                    path="src/agent_mvp/telegram.py",
                    content="new",
                    summary="Update Telegram formatting.",
                ),
            ),
            summary="Summary",
        )

    def respond(self, task: str):  # pragma: no cover - this workflow should not call respond.
        raise AssertionError("respond should not be called for PR tasks")


if __name__ == "__main__":
    unittest.main()
