from datetime import datetime
import unittest
from zoneinfo import ZoneInfo

from src.agent_mvp.reminders import ReminderParser


class ReminderParserTest(unittest.TestCase):
    def test_parse_relative_reminder(self) -> None:
        parser = ReminderParser("Europe/Moscow")
        now = datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))

        reminder = parser.parse("/remind через 10 минут проверить сборку", now=now)

        self.assertEqual(reminder.text, "проверить сборку")
        self.assertEqual(reminder.human_time, "через 10 мин.")
        self.assertEqual(reminder.due_at, "2026-05-31T12:10:00+03:00")

    def test_parse_relative_minute_without_amount(self) -> None:
        parser = ReminderParser("Europe/Moscow")
        now = datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))

        reminder = parser.parse("Посмотри погоду в Питере через минуту и скажи мне.", now=now)

        self.assertEqual(reminder.text, "Посмотри погоду в Питере и скажи мне")
        self.assertEqual(reminder.human_time, "через 1 мин.")
        self.assertEqual(reminder.due_at, "2026-05-31T12:01:00+03:00")

    def test_parse_relative_hour_without_amount(self) -> None:
        parser = ReminderParser("Europe/Moscow")
        now = datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))

        reminder = parser.parse("через час проверить погоду", now=now)

        self.assertEqual(reminder.text, "проверить погоду")
        self.assertEqual(reminder.human_time, "через 1 ч.")
        self.assertEqual(reminder.due_at, "2026-05-31T13:00:00+03:00")

    def test_parse_natural_reminder(self) -> None:
        parser = ReminderParser("Europe/Moscow")
        now = datetime(2026, 5, 31, 12, 0, tzinfo=ZoneInfo("Europe/Moscow"))

        reminder = parser.parse("напомни мне завтра 09:30 написать план", now=now)

        self.assertEqual(reminder.text, "написать план")
        self.assertEqual(reminder.due_at, "2026-06-01T09:30:00+03:00")


if __name__ == "__main__":
    unittest.main()
