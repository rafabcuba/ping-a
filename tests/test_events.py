import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ping_a.events import EventDecider


class TestEvents(unittest.TestCase):
    def test_reply_mode(self):
        decider = EventDecider("reply")
        self.assertEqual(decider.on_result(True, 12.0), "reply")
        self.assertIsNone(decider.on_result(False, None))

    def test_reply_mode_with_threshold(self):
        decider = EventDecider("reply", latency_threshold_ms=100)
        self.assertIsNone(decider.on_result(True, 50.0))
        self.assertEqual(decider.on_result(True, 150.0), "reply")
        self.assertIsNone(decider.on_result(True, 100.0))

    def test_timeout_mode(self):
        decider = EventDecider("timeout")
        self.assertIsNone(decider.on_result(True, 10.0))
        self.assertEqual(decider.on_result(False, None), "timeout")
        self.assertEqual(decider.on_result(False, None), "timeout")

    def test_change_mode(self):
        decider = EventDecider("change")
        self.assertIsNone(decider.on_result(True, 10.0))
        self.assertEqual(decider.on_result(False, None), "down")
        self.assertIsNone(decider.on_result(False, None))
        self.assertEqual(decider.on_result(True, 11.0), "up")

    def test_failure_mode(self):
        decider = EventDecider("failure")
        self.assertEqual(decider.on_result(False, None), "down")
        self.assertIsNone(decider.on_result(False, None))
        self.assertEqual(decider.on_result(True, 10.0), "up")
        self.assertIsNone(decider.on_result(True, 12.0))

    def test_failure_mode_starts_up(self):
        decider = EventDecider("failure")
        self.assertIsNone(decider.on_result(True, 10.0))
        self.assertEqual(decider.on_result(False, None), "down")

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            EventDecider("nope")


if __name__ == "__main__":
    unittest.main()
