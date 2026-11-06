import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ping_a.prober import build_command, parse_reply


class TestProber(unittest.TestCase):
    def test_parse_ipv4_reply(self):
        output = (
            "PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.\n"
            "64 bytes from 1.1.1.1: icmp_seq=1 ttl=57 time=11.8 ms\n"
        )
        parsed = parse_reply(output)
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed["rtt_ms"], 11.8)
        self.assertEqual(parsed["ttl"], 57)
        self.assertEqual(parsed["size"], 64)

    def test_parse_ipv6_reply(self):
        output = (
            "PING ::1 (::1) 56 data bytes\n"
            "64 bytes from ::1: icmp_seq=1 ttl=64 time=0.181 ms\n"
        )
        parsed = parse_reply(output)
        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed["rtt_ms"], 0.181)
        self.assertEqual(parsed["ttl"], 64)

    def test_parse_without_reply(self):
        output = (
            "PING 192.0.2.1 (192.0.2.1) 56(84) bytes of data.\n"
            "\n--- 192.0.2.1 ping statistics ---\n"
            "1 packets transmitted, 0 received, 100% packet loss\n"
        )
        self.assertIsNone(parse_reply(output))

    def test_build_command_ipv4(self):
        command = build_command("example.com", 2.0, 56, ipv6=False)
        self.assertEqual(command[0], "ping")
        self.assertIn("-n", command)
        self.assertIn("-c", command)
        self.assertIn("2", command)
        self.assertIn("56", command)
        self.assertNotIn("-6", command)
        self.assertEqual(command[-1], "example.com")

    def test_build_command_ipv6_and_decimal_timeout(self):
        command = build_command("::1", 0.5, 56, ipv6=True)
        self.assertIn("-6", command)
        self.assertIn("0.5", command)
        self.assertEqual(command[-1], "::1")


if __name__ == "__main__":
    unittest.main()
