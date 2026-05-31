# AST Summary: `src/agent_mvp/specialist_workflows.py`

Structural cache for future agents; update when the source file shape changes materially.

## Module Docstring

_None._

## Exported Symbols

- `SpecialistWorkflows`

## Classes

### `SpecialistWorkflows`

Owns bounded specialist workflows extracted from `AgentWorkspaceApp`: Weather delegation, Planner/reminder handling, Senior Python Developer delegation, GitHub file/PR/merge commands, deferred intent execution, weather parsing helpers, and developer command parsers. It receives the app composition root and renderer, then reads runtime dependencies through properties so tests can still replace `app.telegram`, `app.weather`, `app.github`, or `app.python_developer`.

Properties:

- `config`
- `store`
- `assistant`
- `python_developer`
- `github`
- `weather`
- `reminder_parser`
- `timezone`

Methods:

- `def __init__(self, app: Any, renderer: Any) -> None`
- `def emit_agent_message(self, chat_id: int, request_id: str, conversation_id: str, text: str, reply_to_message_id: int | None = None, agent_id: str = PERSONAL_ASSISTANT_ID) -> None`
- `def emit_delegation_event(self, from_agent_id: str, to_agent_id: str, task: str, request_id: str, conversation_id: str, chat_id: int) -> None`
- `def handle_python_file_read(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def handle_python_file_change(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def handle_python_merge_pr(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def handle_python_pull_request(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def delegate_python_developer_from_assistant(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def delegate_python_developer_to_chat(self, chat_id: int, text: str, request_id: str, conversation_id: str, reply_to_message_id: int | None = None, final_prefix: str = '[Assistant] Senior Python Developer вернул результат:') -> None`
- `def delegate_weather_from_assistant(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def delegate_weather_to_chat(self, chat_id: int, text: str, request_id: str, conversation_id: str, reply_to_message_id: int | None = None, final_prefix: str = '[Assistant] По данным Weather:') -> None`
- `def delegate_reminder_from_assistant(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str) -> None`
- `def handle_weather(self, chat_id: int, text: str, request_id: str, conversation_id: str, delegated: bool = False) -> str`
- `def handle_reminder(self, message: TelegramMessage, text: str, request_id: str, conversation_id: str, delegated: bool = False) -> str | None`
- `def handle_reminders_list(self, message: TelegramMessage, request_id: str, conversation_id: str) -> None`
- `def process_due_reminders(self) -> None`
- `def handle_deferred_intent(self, chat_id: int, text: str, request_id: str, conversation_id: str) -> None`
- `def extract_weather_location(self, text: str) -> str`
- `def normalize_location(self, location: str) -> str`
- `def looks_like_weather_request(self, text: str) -> bool`
- `def looks_like_reminder_request(self, text: str) -> bool`
- `def can_parse_reminder(self, text: str) -> bool`
- `def extract_command_payload(self, text: str, command: str) -> str`
- `def add_developer_project_context(self, task: str) -> str`
- `def should_open_pr_from_developer_task(self, task: str) -> bool`
- `def try_handle_developer_pr_task(self, chat_id: int, task: str, user_task: str, request_id: str, conversation_id: str) -> bool`
- `def parse_python_pr_command(self, text: str) -> tuple[str, str, str, str] | None`
- `def parse_python_file_command(self, text: str) -> tuple[str, str, str] | None`
- `def parse_python_change_file_command(self, text: str) -> tuple[str, str, str, str, str] | None`
- `def parse_python_merge_pr_command(self, text: str) -> tuple[str, int] | None`
