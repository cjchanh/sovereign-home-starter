"""Offline doctor is a product grader. Live Docker/Ollama/Frigate are env."""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCTOR = ROOT / "doctor.sh"


class DoctorTests(unittest.TestCase):
    def test_help_exits_zero(self):
        cp = subprocess.run(
            ["bash", str(DOCTOR), "--help"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(cp.returncode, 0, cp.stderr)
        self.assertIn("--offline", cp.stdout)

    def test_unknown_flag_exits_2(self):
        cp = subprocess.run(
            ["bash", str(DOCTOR), "--live-frigate"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(cp.returncode, 2)
        self.assertIn("unknown argument", cp.stderr)

    def test_offline_passes_without_docker_or_ollama(self):
        cp = subprocess.run(
            ["bash", str(DOCTOR), "--offline"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(ROOT),
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("offline product checks passed", cp.stdout)
        self.assertIn("assistant/*.py compiles", cp.stdout)
        self.assertIn("[env]", cp.stdout)
        self.assertNotIn("[FAIL]", cp.stdout)


if __name__ == "__main__":
    unittest.main()
