import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ping_a.stats import Stats


class TestStats(unittest.TestCase):
    def test_empty_stats(self):
        stats = Stats()
        self.assertEqual(stats.transmitted, 0)
        self.assertEqual(stats.received, 0)
        self.assertEqual(stats.loss_percent, 0.0)
        self.assertIsNone(stats.rtt_stats())
        self.assertIn("0 paquetes transmitidos", stats.summary("host"))

    def test_counts_loss_and_mdev(self):
        stats = Stats()
        stats.record(True, 10.0)
        stats.record(False)
        stats.record(True, 20.0)
        stats.record(True, 30.0)

        self.assertEqual(stats.transmitted, 4)
        self.assertEqual(stats.received, 3)
        self.assertEqual(stats.lost, 1)
        self.assertAlmostEqual(stats.loss_percent, 25.0)

        minimum, average, maximum, mdev = stats.rtt_stats()
        self.assertEqual(minimum, 10.0)
        self.assertEqual(average, 20.0)
        self.assertEqual(maximum, 30.0)
        self.assertAlmostEqual(mdev, (200.0 / 3.0) ** 0.5)

    def test_singular_summary(self):
        stats = Stats()
        stats.record(True, 1.5)
        summary = stats.summary("127.0.0.1")
        self.assertIn("1 paquete transmitido, 1 recibido", summary)
        self.assertIn("rtt mín/med/máx/desv", summary)


if __name__ == "__main__":
    unittest.main()
