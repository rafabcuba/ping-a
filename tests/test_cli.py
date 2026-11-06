import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


@unittest.skipUnless(shutil.which("ping"), "ping no está disponible")
class TestCli(unittest.TestCase):
    def run_cli(self, *arguments, timeout=25):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = (
            str(SRC)
            + os.pathsep
            + environment.get("PYTHONPATH", "")
        )
        return subprocess.run(
            [sys.executable, "-m", "ping_a", *arguments],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )

    def test_single_ping_with_null_backend(self):
        completed = self.run_cli(
            "-c", "1", "-i", "0.2", "--backend", "null", "127.0.0.1"
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("icmp_seq=1", completed.stdout)
        self.assertIn("1 paquete transmitido", completed.stdout)
        self.assertIn("[audio: null]", completed.stdout)

    def test_json_output(self):
        completed = self.run_cli(
            "-c",
            "1",
            "-i",
            "0.2",
            "--backend",
            "null",
            "--json",
            "127.0.0.1",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        lines = [
            line for line in completed.stdout.splitlines() if line.strip()
        ]
        payload = json.loads(lines[-1])
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["seq"], 1)
        self.assertEqual(payload["event"], "reply")

    def test_bad_host_exits_2(self):
        completed = self.run_cli(
            "-c", "1", "--backend", "null", "host.invalido.invalid"
        )
        self.assertEqual(completed.returncode, 2)

    def test_version(self):
        completed = self.run_cli("--version")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("ping-a", completed.stdout)


if __name__ == "__main__":
    unittest.main()
