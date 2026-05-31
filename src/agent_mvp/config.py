from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    telegram_allowed_chat_id: int | None
    openai_api_key: str | None
    openai_model: str | None
    python_developer_api_key: str | None
    python_developer_model: str | None
    python_developer_base_url: str
    database_path: str
    poll_timeout_seconds: int
    poll_interval_seconds: int
    public_tool_events: bool
    local_timezone: str
    weather_default_location: str

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key and self.openai_model)

    @property
    def python_developer_enabled(self) -> bool:
        return bool(self.python_developer_api_key and self.python_developer_model)


def load_config() -> Config:
    load_dotenv()

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required. Add it to .env.")

    return Config(
        telegram_bot_token=token,
        telegram_allowed_chat_id=_optional_int(os.getenv("TELEGRAM_ALLOWED_CHAT_ID")),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL") or None,
        python_developer_api_key=os.getenv("PYTHON_DEVELOPER_API_KEY") or None,
        python_developer_model=os.getenv("PYTHON_DEVELOPER_MODEL") or None,
        python_developer_base_url=os.getenv("PYTHON_DEVELOPER_BASE_URL", "https://api.openai.com/v1"),
        database_path=os.getenv("DATABASE_PATH", ".data/agent_workspace.sqlite3"),
        poll_timeout_seconds=int(os.getenv("POLL_TIMEOUT_SECONDS", "30")),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "1")),
        public_tool_events=_bool(os.getenv("PUBLIC_TOOL_EVENTS"), default=True),
        local_timezone=os.getenv("LOCAL_TIMEZONE", "Europe/Moscow"),
        weather_default_location=os.getenv("WEATHER_DEFAULT_LOCATION", "Moscow"),
    )
