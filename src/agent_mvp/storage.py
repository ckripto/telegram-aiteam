from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .events import Event


class EventStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        db_parent = Path(database_path).parent
        if str(db_parent) not in {"", "."}:
            db_parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists events (
                    id text primary key,
                    event_type text not null,
                    actor_type text not null,
                    actor_id text not null,
                    target_id text,
                    visibility text not null,
                    request_id text not null,
                    conversation_id text not null,
                    telegram_chat_id integer,
                    telegram_message_id integer,
                    payload_json text not null,
                    created_at text not null
                )
                """
            )
            conn.execute(
                """
                create index if not exists idx_events_request
                on events (request_id, created_at)
                """
            )
            conn.execute(
                """
                create index if not exists idx_events_conversation
                on events (conversation_id, created_at)
                """
            )
            conn.execute(
                """
                create table if not exists reminders (
                    id text primary key,
                    chat_id integer not null,
                    user_id text,
                    text text not null,
                    due_at text not null,
                    status text not null,
                    created_at text not null,
                    sent_at text
                )
                """
            )
            conn.execute(
                """
                create index if not exists idx_reminders_due
                on reminders (status, due_at)
                """
            )

    def append(self, event: Event) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into events (
                    id,
                    event_type,
                    actor_type,
                    actor_id,
                    target_id,
                    visibility,
                    request_id,
                    conversation_id,
                    telegram_chat_id,
                    telegram_message_id,
                    payload_json,
                    created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.event_type,
                    event.actor_type,
                    event.actor_id,
                    event.target_id,
                    event.visibility,
                    event.request_id,
                    event.conversation_id,
                    event.telegram_chat_id,
                    event.telegram_message_id,
                    event.payload_json(),
                    event.created_at,
                ),
            )

    def count_events(self) -> int:
        with self._connect() as conn:
            row = conn.execute("select count(*) as count from events").fetchone()
            return int(row["count"])

    def last_events(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from events
                order by created_at desc
                limit ?
                """,
                (limit,),
            ).fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def create_reminder(
        self,
        reminder_id: str,
        chat_id: int,
        user_id: str | None,
        text: str,
        due_at: str,
        created_at: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert into reminders (
                    id,
                    chat_id,
                    user_id,
                    text,
                    due_at,
                    status,
                    created_at
                ) values (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (reminder_id, chat_id, user_id, text, due_at, created_at),
            )

    def due_reminders(self, now_iso: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from reminders
                where status = 'pending' and due_at <= ?
                order by due_at asc
                limit ?
                """,
                (now_iso, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def pending_reminders(self, chat_id: int, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select *
                from reminders
                where status = 'pending' and chat_id = ?
                order by due_at asc
                limit ?
                """,
                (chat_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_reminder_sent(self, reminder_id: str, sent_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update reminders
                set status = 'sent', sent_at = ?
                where id = ?
                """,
                (sent_at, reminder_id),
            )
