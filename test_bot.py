import copy
import unittest
from bot import deliver, slack_text


class Store:
    def __init__(self, state=None):
        self.state = copy.deepcopy(state)

    def read(self):
        return copy.deepcopy(self.state)

    def write(self, state):
        self.state = copy.deepcopy(state)


class DeliveryTests(unittest.TestCase):
    def test_first_run_and_repeat_do_not_send_old_articles(self):
        store = Store()
        sent = []
        news = {"1": {"id": 1, "title": "Existing"}}
        deliver(news, store, sent.append)
        deliver(news, store, sent.append)
        self.assertEqual(sent, [])

    def test_multiple_new_items_sent_once_oldest_first(self):
        store = Store({"version": 1, "seen": ["1"], "pending": None})
        sent = []
        news = {"3": {"id": 3, "title": "Third"}, "2": {"id": 2, "title": "Second"}}
        deliver(news, store, sent.append)
        deliver(news, store, sent.append)
        self.assertEqual([item["id"] for item in sent], [2, 3])

    def test_unknown_outcome_is_not_retried(self):
        store = Store({"version": 1, "seen": [], "pending": None})
        news = {"2": {"id": 2, "title": "New"}}
        calls = []
        def fail(item):
            calls.append(item)
            raise RuntimeError("Timeout")
        with self.assertRaises(RuntimeError):
            deliver(news, store, fail)
        with self.assertRaises(RuntimeError):
            deliver(news, store, fail)
        self.assertEqual(len(calls), 1)
        self.assertEqual(store.state["pending"]["id"], "2")

    def test_title_cannot_inject_slack_mentions(self):
        text = slack_text({"id": 1, "title": "Test <!channel> &amp; title"})
        self.assertNotIn("<!channel>", text)
        self.assertIn("&lt;!channel&gt;", text)


if __name__ == "__main__":
    unittest.main()
