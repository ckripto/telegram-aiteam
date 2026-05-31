import unittest

from src.agent_mvp.telegram import SAFE_MESSAGE_LIMIT, split_telegram_message


class TelegramMessageTest(unittest.TestCase):
    def test_splits_long_messages_under_safe_limit(self) -> None:
        text = ("line\n" * 1200).strip()

        chunks = split_telegram_message(text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= SAFE_MESSAGE_LIMIT for chunk in chunks))
        self.assertEqual("".join(chunks).replace("\n", ""), text.replace("\n", ""))


if __name__ == "__main__":
    unittest.main()
