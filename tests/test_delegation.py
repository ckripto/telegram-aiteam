import tempfile
import unittest

from src.agent_mvp.agent_registry import (
    PLANNER_ASSISTANT_ID,
    WEATHER_ASSISTANT_ID,
    format_assistant_agent_context,
)
from src.agent_mvp.app import AgentMvpApp
from src.agent_mvp.config import Config
from src.agent_mvp.telegram import TelegramMessage
from src.agent_mvp.weather import WeatherForecast


def test_config(database_path: str) -> Config:
    return Config(
        telegram_bot_token="test",
        telegram_allowed_chat_id=None,
        openai_api_key=None,
        openai_model=None,
        python_developer_api_key=None,
        python_developer_model=None,
        python_developer_base_url="https://api.openai.com/v1",
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


if __name__ == "__main__":
    unittest.main()
