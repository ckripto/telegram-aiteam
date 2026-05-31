import tempfile
import unittest

from src.agent_mvp.events import Event
from src.agent_mvp.events import utc_now
from src.agent_mvp.storage import EventStore


class EventStoreTest(unittest.TestCase):
    def test_append_and_count_event(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            store = EventStore(tmp.name)
            event = Event.create(
                event_type="agent_message",
                actor_type="agent",
                actor_id="personal_assistant",
                visibility="public",
                payload={"text": "hello"},
                request_id="req_1",
                conversation_id="tg_1",
            )

            store.append(event)

            self.assertEqual(store.count_events(), 1)
            self.assertEqual(store.last_events()[0]["payload"]["text"], "hello")

    def test_reminder_lifecycle(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp:
            store = EventStore(tmp.name)
            store.create_reminder(
                reminder_id="rem_1",
                chat_id=123,
                user_id="42",
                text="check build",
                due_at="2026-05-31T12:00:00+03:00",
                created_at=utc_now(),
            )

            self.assertEqual(len(store.pending_reminders(123)), 1)
            self.assertEqual(len(store.due_reminders("2026-05-31T12:01:00+03:00")), 1)

            store.mark_reminder_sent("rem_1", utc_now())

            self.assertEqual(store.pending_reminders(123), [])
            self.assertEqual(store.due_reminders("2026-05-31T12:02:00+03:00"), [])


if __name__ == "__main__":
    unittest.main()
