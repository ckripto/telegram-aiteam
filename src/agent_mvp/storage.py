from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .events import Event, utc_now


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]


MIGRATIONS = (
    Migration(
        version=1,
        name="initial_events_and_reminders",
        statements=(
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
            """,
            """
            create index if not exists idx_events_request
            on events (request_id, created_at)
            """,
            """
            create index if not exists idx_events_conversation
            on events (conversation_id, created_at)
            """,
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
            """,
            """
            create index if not exists idx_reminders_due
            on reminders (status, due_at)
            """,
        ),
    ),
    Migration(
        version=2,
        name="memory_data_model_tables",
        statements=(
            """
            create table if not exists workspaces (
                id text primary key,
                name text not null,
                created_at text not null
            )
            """,
            """
            create table if not exists telegram_chats (
                id text primary key,
                workspace_id text not null,
                telegram_chat_id integer not null,
                title text,
                created_at text not null,
                is_active integer not null default 1
            )
            """,
            """
            create unique index if not exists idx_telegram_chats_telegram_id
            on telegram_chats (telegram_chat_id)
            """,
            """
            create index if not exists idx_telegram_chats_workspace
            on telegram_chats (workspace_id, is_active)
            """,
            """
            create table if not exists users (
                id text primary key,
                workspace_id text not null,
                telegram_user_id integer,
                display_name text,
                role text,
                created_at text not null
            )
            """,
            """
            create unique index if not exists idx_users_workspace_telegram_id
            on users (workspace_id, telegram_user_id)
            where telegram_user_id is not null
            """,
            """
            create table if not exists agents (
                id text primary key,
                workspace_id text not null,
                display_name text not null,
                role text not null,
                config_json text not null default '{}',
                model_env text,
                api_key_env text,
                base_url_env text,
                is_active integer not null default 1,
                created_at text not null,
                updated_at text not null
            )
            """,
            """
            create index if not exists idx_agents_workspace_active
            on agents (workspace_id, is_active)
            """,
            """
            create table if not exists agent_runs (
                id text primary key,
                workspace_id text not null,
                agent_id text not null,
                request_id text not null,
                status text not null,
                input_event_ids_json text not null default '[]',
                output_event_ids_json text not null default '[]',
                model text,
                started_at text not null,
                completed_at text,
                error text
            )
            """,
            """
            create index if not exists idx_agent_runs_request
            on agent_runs (request_id, started_at)
            """,
            """
            create table if not exists tool_calls (
                id text primary key,
                workspace_id text not null,
                agent_id text not null,
                capability text not null,
                mcp_server text,
                mcp_tool text,
                arguments_redacted_json text not null default '{}',
                status text not null,
                result_summary text,
                confirmation_id text,
                started_at text not null,
                completed_at text,
                error text
            )
            """,
            """
            create index if not exists idx_tool_calls_workspace_status
            on tool_calls (workspace_id, status, started_at)
            """,
            """
            create table if not exists confirmations (
                id text primary key,
                workspace_id text not null,
                request_id text not null,
                agent_id text not null,
                capability text not null,
                action_summary text not null,
                status text not null,
                requested_by_event_id text,
                approved_by_user_id text,
                created_at text not null,
                decided_at text
            )
            """,
            """
            create index if not exists idx_confirmations_status
            on confirmations (workspace_id, status, created_at)
            """,
            """
            create table if not exists memories (
                id text primary key,
                workspace_id text not null,
                scope_type text not null,
                scope_id text,
                key text not null,
                value text not null,
                source_event_id text,
                confidence real,
                created_at text not null,
                updated_at text not null
            )
            """,
            """
            create index if not exists idx_memories_scope
            on memories (workspace_id, scope_type, scope_id, key)
            """,
            """
            create table if not exists projects (
                id text primary key,
                workspace_id text not null,
                name text not null,
                description text,
                status text not null,
                project_agent_id text,
                created_at text not null,
                updated_at text not null
            )
            """,
            """
            create index if not exists idx_projects_workspace_status
            on projects (workspace_id, status, name)
            """,
            """
            create table if not exists delegations (
                id text primary key,
                workspace_id text not null,
                project_id text,
                request_id text not null,
                from_agent_id text not null,
                to_agent_id text not null,
                task text not null,
                status text not null,
                created_event_id text,
                result_event_id text,
                created_at text not null,
                completed_at text
            )
            """,
            """
            create index if not exists idx_delegations_request
            on delegations (request_id, created_at)
            """,
            """
            create index if not exists idx_delegations_status
            on delegations (workspace_id, status, created_at)
            """,
        ),
    ),
)


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists schema_migrations (
            version integer primary key,
            name text not null,
            applied_at text not null
        )
        """
    )
    rows = conn.execute("select version from schema_migrations").fetchall()
    applied: set[int] = set()
    for row in rows:
        version = row["version"] if isinstance(row, sqlite3.Row) else row[0]
        applied.add(int(version))
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        for statement in migration.statements:
            conn.execute(statement)
        conn.execute(
            """
            insert into schema_migrations (version, name, applied_at)
            values (?, ?, ?)
            """,
            (migration.version, migration.name, utc_now()),
        )


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
            run_migrations(conn)

    def applied_migrations(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select version, name, applied_at
                from schema_migrations
                order by version
                """
            ).fetchall()
        return [dict(row) for row in rows]

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
