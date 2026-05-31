from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class Event:
    id: str
    event_type: str
    actor_type: str
    actor_id: str
    visibility: str
    payload: dict[str, Any]
    request_id: str
    conversation_id: str
    created_at: str
    telegram_chat_id: int | None = None
    telegram_message_id: int | None = None
    target_id: str | None = None

    @classmethod
    def create(
        cls,
        event_type: str,
        actor_type: str,
        actor_id: str,
        visibility: str,
        payload: dict[str, Any],
        request_id: str,
        conversation_id: str,
        telegram_chat_id: int | None = None,
        telegram_message_id: int | None = None,
        target_id: str | None = None,
    ) -> "Event":
        return cls(
            id=new_id("evt"),
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            visibility=visibility,
            payload=payload,
            request_id=request_id,
            conversation_id=conversation_id,
            created_at=utc_now(),
            telegram_chat_id=telegram_chat_id,
            telegram_message_id=telegram_message_id,
            target_id=target_id,
        )

    def payload_json(self) -> str:
        return json.dumps(self.payload, ensure_ascii=False, sort_keys=True)

