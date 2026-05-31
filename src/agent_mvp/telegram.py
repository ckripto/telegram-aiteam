from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TelegramMessage:
    update_id: int
    chat_id: int
    message_id: int
    text: str
    user_id: int | None
    username: str | None
    first_name: str | None

    @property
    def display_user(self) -> str:
        if self.username:
            return f"@{self.username}"
        if self.first_name:
            return self.first_name
        if self.user_id is not None:
            return str(self.user_id)
        return "unknown"


class TelegramClient:
    def __init__(self, token: str) -> None:
        self.base_url = f"https://api.telegram.org/bot{token}"

    def _request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=data,
            headers=headers,
            method="POST" if payload is not None else "GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Telegram API error {exc.code}: {error_body}") from exc

        result = json.loads(body)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API error: {result}")
        return result

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self._request("getUpdates", payload)["result"]

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_to_message_id is not None:
            payload["reply_parameters"] = {"message_id": reply_to_message_id}
        result = self._request("sendMessage", payload)["result"]
        return int(result["message_id"])


def parse_message(update: dict[str, Any]) -> TelegramMessage | None:
    message = update.get("message")
    if not message:
        return None
    text = message.get("text")
    if not text:
        return None

    chat = message.get("chat", {})
    user = message.get("from", {})
    return TelegramMessage(
        update_id=int(update["update_id"]),
        chat_id=int(chat["id"]),
        message_id=int(message["message_id"]),
        text=text,
        user_id=user.get("id"),
        username=user.get("username"),
        first_name=user.get("first_name"),
    )

