# AST Summary: `src/agent_mvp/storage.py`

Structural cache for future agents; update when the source file shape changes materially.

## Module Docstring

_None._

## Exported Symbols

- `Migration`
- `MIGRATIONS`
- `run_migrations`
- `EventStore`

## Top-Level Data

- `MIGRATIONS`: tuple of immutable schema migrations.
  - Version 1: current `events` and `reminders` tables plus indexes.
  - Version 2: future memory-data tables from `docs/memory-data.md`.

## Top-Level Functions

- `def run_migrations(conn: sqlite3.Connection) -> None`

## Classes

### `Migration`

Dataclass fields:

- `version: int`
- `name: str`
- `statements: tuple[str, ...]`

### `EventStore`

Methods:

- `def __init__(self, database_path: str) -> None`
- `def _connect(self) -> sqlite3.Connection`
- `def _init_db(self) -> None`
- `def applied_migrations(self) -> list[dict[str, Any]]`
- `def append(self, event: Event) -> None`
- `def count_events(self) -> int`
- `def last_events(self, limit: int = 10) -> list[dict[str, Any]]`
- `def create_reminder(self, reminder_id: str, chat_id: int, user_id: str | None, text: str, due_at: str, created_at: str) -> None`
- `def due_reminders(self, now_iso: str, limit: int = 20) -> list[dict[str, Any]]`
- `def pending_reminders(self, chat_id: int, limit: int = 10) -> list[dict[str, Any]]`
- `def mark_reminder_sent(self, reminder_id: str, sent_at: str) -> None`
