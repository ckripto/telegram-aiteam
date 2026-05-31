from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ReminderRequest:
    due_at: str
    text: str
    human_time: str


class ReminderParser:
    def __init__(self, timezone_name: str) -> None:
        self.timezone = ZoneInfo(timezone_name)

    def parse(self, raw_text: str, now: datetime | None = None) -> ReminderRequest:
        now = now or datetime.now(self.timezone)
        text = self._strip_command(raw_text)
        if not text:
            raise ValueError("Напишите время и текст напоминания.")

        relative = self._parse_relative(text, now)
        if relative is not None:
            return relative

        absolute = self._parse_absolute(text, now)
        if absolute is not None:
            return absolute

        raise ValueError(
            "Не понял время. Используйте, например: "
            "/remind через 10 минут проверить сборку или /remind 2026-06-01 09:30 созвон."
        )

    def _strip_command(self, raw_text: str) -> str:
        text = raw_text.strip()
        if text.lower().startswith("/remind"):
            parts = text.split(maxsplit=1)
            return parts[1].strip() if len(parts) > 1 else ""
        lowered = text.lower()
        for prefix in ("напомни мне", "напомнить мне", "напомни", "напомнить"):
            if lowered.startswith(prefix):
                return text[len(prefix):].strip()
        return text

    def _parse_relative(self, text: str, now: datetime) -> ReminderRequest | None:
        match = re.match(
            r"(?i)^через\s+(\d+)\s+(минут(?:у|ы)?|час(?:а|ов)?|дн(?:я|ей|ь)?)\s+(.+)$",
            text,
        )
        if not match:
            return None

        amount = int(match.group(1))
        unit = match.group(2).lower()
        reminder_text = match.group(3).strip()
        if unit.startswith("минут"):
            due_at = now + timedelta(minutes=amount)
            human = f"через {amount} мин."
        elif unit.startswith("час"):
            due_at = now + timedelta(hours=amount)
            human = f"через {amount} ч."
        else:
            due_at = now + timedelta(days=amount)
            human = f"через {amount} дн."

        return ReminderRequest(due_at=due_at.isoformat(), text=reminder_text, human_time=human)

    def _parse_absolute(self, text: str, now: datetime) -> ReminderRequest | None:
        match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+(.+)$", text)
        if match:
            date_part, time_part, reminder_text = match.groups()
            due_at = datetime.fromisoformat(f"{date_part}T{time_part}:00").replace(tzinfo=self.timezone)
            return ReminderRequest(
                due_at=due_at.isoformat(),
                text=reminder_text.strip(),
                human_time=due_at.strftime("%Y-%m-%d %H:%M"),
            )

        match = re.match(r"(?i)^сегодня\s+(\d{1,2}:\d{2})\s+(.+)$", text)
        if match:
            time_part, reminder_text = match.groups()
            hour, minute = [int(part) for part in time_part.split(":", 1)]
            due_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if due_at <= now:
                due_at += timedelta(days=1)
            return ReminderRequest(
                due_at=due_at.isoformat(),
                text=reminder_text.strip(),
                human_time=due_at.strftime("%Y-%m-%d %H:%M"),
            )

        match = re.match(r"(?i)^завтра\s+(\d{1,2}:\d{2})\s+(.+)$", text)
        if match:
            time_part, reminder_text = match.groups()
            hour, minute = [int(part) for part in time_part.split(":", 1)]
            due_at = (now + timedelta(days=1)).replace(hour=hour, minute=minute, second=0, microsecond=0)
            return ReminderRequest(
                due_at=due_at.isoformat(),
                text=reminder_text.strip(),
                human_time=due_at.strftime("%Y-%m-%d %H:%M"),
            )

        return None
