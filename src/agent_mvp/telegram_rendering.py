from __future__ import annotations

from typing import Any

from .agent_registry import PERSONAL_ASSISTANT_ID
from .events import Event


class TelegramEventRenderer:
    def __init__(self, app: Any) -> None:
        self.app = app

    def emit_agent_message(
        self,
        chat_id: int,
        request_id: str,
        conversation_id: str,
        text: str,
        reply_to_message_id: int | None = None,
        agent_id: str = PERSONAL_ASSISTANT_ID,
    ) -> None:
        message_id = self.app.telegram.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
        )
        self.app.store.append(
            Event.create(
                event_type="agent_message",
                actor_type="agent",
                actor_id=agent_id,
                visibility="public",
                payload={"text": text},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=chat_id,
                telegram_message_id=message_id,
            )
        )

    def emit_delegation_event(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task: str,
        request_id: str,
        conversation_id: str,
        chat_id: int,
    ) -> None:
        self.app.store.append(
            Event.create(
                event_type="agent_delegation_requested",
                actor_type="agent",
                actor_id=from_agent_id,
                target_id=to_agent_id,
                visibility="public",
                payload={"task": task},
                request_id=request_id,
                conversation_id=conversation_id,
                telegram_chat_id=chat_id,
            )
        )
