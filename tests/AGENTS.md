# Test Suite Agent Memory

## PURPOSE

`tests` contains the `unittest` coverage for routing, delegation, GitHub gateway behavior, reminders, storage, Telegram message splitting, and specialist runtime fallbacks. Use it to lock down behavior before changing orchestration or tool access.

## KEY FILES

- `test_delegation.py`: integration-style tests for Assistant delegation, delayed weather flow, default GitHub repo behavior, and developer PR workflow.
- `test_github_gateway.py`: GitHub token, repository resolution, and permission diagnostics tests.
- `test_telegram.py`: long Telegram message splitting tests.
- `test_python_developer.py`: Senior Python Developer registry visibility and offline credential fallback tests.
- `test_assistant.py`: Assistant offline prompt generation behavior.
- `test_reminders.py`: reminder parser coverage.
- `test_storage.py`: SQLite event/reminder persistence coverage.

## RULES

- Use standard-library `unittest`; no pytest dependency is currently configured.
- Keep tests deterministic and offline by replacing Telegram, weather, GitHub, and model clients with fakes.
- Create temporary database files for tests that touch `EventStore`.
- When adding a capability, test both the happy path and the missing-configuration fallback.

## GOTCHAS

- Several tests instantiate `Config` directly; adding required config fields needs synchronized test updates.
- The test suite assumes package imports through `src.agent_mvp`.
- GitHub and model tests must not call the network.
- `FakeTelegram.send_message` returns incrementing ids and stores text only; it does not emulate Telegram parse modes or API errors.
