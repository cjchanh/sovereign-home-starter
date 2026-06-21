"""Smoke tests for the assistant stack — run on your own box to confirm it works.

    python3 -m unittest discover -s tests
    # or:  python3 tests/test_assistant.py

Zero third-party deps (stdlib unittest). Network calls (Ollama, Telegram, Frigate)
are mocked, so these pass offline and prove the LOGIC, not your live services. Use
./doctor.sh to check the live services.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "assistant"))

import alert_watcher  # noqa: E402
import config  # noqa: E402
import memory  # noqa: E402
import notify  # noqa: E402
import sitrep  # noqa: E402


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _mock_urlopen(body: bytes, capture: dict | None = None):
    def fake(req, timeout=0):
        if capture is not None and getattr(req, "data", None):
            capture["body"] = json.loads(req.data.decode())
        return _Resp(body)

    return fake


def _frigate_backend(events: list[dict]):
    """Faithful Frigate /api/events: newest-first, capped at LIMIT, honors after/before."""

    def be(nvr_url, after, before=None):
        sel = [
            e
            for e in events
            if e["start_time"] > after and (before is None or e["start_time"] < before)
        ]
        sel.sort(key=lambda e: e["start_time"], reverse=True)
        return sel[: alert_watcher.LIMIT]

    return be


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.path = str(Path(tempfile.mkdtemp()) / "mem.jsonl")

    def test_roundtrip_and_kind_filter(self):
        memory.remember(self.path, "buy coffee", kind="todo")
        memory.remember(self.path, "gate squeaks", kind="note")
        self.assertEqual([e.text for e in memory.load(self.path, kind="todo")], ["buy coffee"])
        self.assertEqual(len(memory.load(self.path)), 2)

    def test_missing_file_returns_empty(self):
        self.assertEqual(memory.load("/no/such/file.jsonl"), [])

    def test_malformed_line_skipped(self):
        Path(self.path).write_text('{"bad json\n{"ts":1,"kind":"note","text":"ok"}\n')
        self.assertEqual([e.text for e in memory.load(self.path)], ["ok"])


class ConfigTests(unittest.TestCase):
    def test_defaults_when_missing(self):
        cfg = config.load_config(None)
        self.assertEqual(cfg["model"], "qwen2.5:7b")
        self.assertIn("notify", cfg)

    def test_malformed_config_falls_back(self):
        p = str(Path(tempfile.mkdtemp()) / "bad.json")
        Path(p).write_text("{ not json,, }")
        self.assertEqual(config.load_config(p)["model"], "qwen2.5:7b")

    def test_non_dict_sitrep_ignored(self):
        p = str(Path(tempfile.mkdtemp()) / "c.json")
        Path(p).write_text(json.dumps({"sitrep": False, "model": "llama3:8b"}))
        cfg = config.load_config(p)
        self.assertEqual(cfg["model"], "llama3:8b")
        self.assertIsInstance(cfg["sitrep"], dict)


class NotifyTests(unittest.TestCase):
    def test_no_creds_is_noop(self):
        self.assertFalse(notify.send("hi", {"notify": {}}))
        self.assertFalse(notify.send("hi", None))

    def test_success_path(self):
        orig = urllib.request.urlopen
        urllib.request.urlopen = _mock_urlopen(b'{"ok":true}')
        try:
            self.assertTrue(
                notify.send("hi", {"notify": {"telegram_bot_token": "t", "telegram_chat_id": "1"}})
            )
        finally:
            urllib.request.urlopen = orig

    def test_utf16_truncation(self):
        cap: dict = {}
        orig = urllib.request.urlopen
        urllib.request.urlopen = _mock_urlopen(b'{"ok":true}', cap)
        try:
            notify.send("🚨" * 5000, {"notify": {"telegram_bot_token": "t", "telegram_chat_id": "1"}})
        finally:
            urllib.request.urlopen = orig
        u16 = len(cap["body"]["text"].encode("utf-16-le")) // 2
        self.assertLessEqual(u16, notify._TELEGRAM_MAX)

    def test_send_photo_no_creds_is_noop(self):
        self.assertFalse(notify.send_photo("caption", b"\xff\xd8\xff", {"notify": {}}))
        self.assertFalse(notify.send_photo("caption", b"\xff\xd8\xff", None))

    def test_send_photo_success_path(self):
        """send_photo returns True when the API returns ok:true."""
        orig = urllib.request.urlopen
        urllib.request.urlopen = _mock_urlopen(b'{"ok":true}')
        try:
            result = notify.send_photo(
                "test caption",
                b"\xff\xd8\xff\xe0",
                {"notify": {"telegram_bot_token": "t", "telegram_chat_id": "1"}},
            )
            self.assertTrue(result)
        finally:
            urllib.request.urlopen = orig

    def test_send_photo_api_failure_returns_false(self):
        """send_photo returns False (no raise) when the API returns ok:false."""
        orig = urllib.request.urlopen
        urllib.request.urlopen = _mock_urlopen(b'{"ok":false,"description":"Bad Request"}')
        try:
            result = notify.send_photo(
                "caption",
                b"\xff\xd8\xff",
                {"notify": {"telegram_bot_token": "t", "telegram_chat_id": "1"}},
            )
            self.assertFalse(result)
        finally:
            urllib.request.urlopen = orig


class AlertWatcherTests(unittest.TestCase):
    def setUp(self):
        self.state = Path(tempfile.mkdtemp()) / "aw.state"
        self._orig_state = alert_watcher.STATE
        self._orig_events = alert_watcher._events
        self._orig_send = notify.send
        self._orig_send_photo = notify.send_photo
        self._orig_fetch_snapshot = alert_watcher._fetch_snapshot
        alert_watcher.STATE = self.state
        sys.argv = ["alert_watcher.py", "--config", "/nonexistent.json"]

    def tearDown(self):
        alert_watcher.STATE = self._orig_state
        alert_watcher._events = self._orig_events
        notify.send = self._orig_send
        notify.send_photo = self._orig_send_photo
        alert_watcher._fetch_snapshot = self._orig_fetch_snapshot

    def _no_snapshot(self, nvr_url: str, event_id: str) -> None:
        """Stub: snapshot unavailable (None) so alerts fall back to text."""
        return None

    def _ok_snapshot(self, nvr_url: str, event_id: str) -> bytes:
        """Stub: always returns fake JPEG bytes."""
        return b"\xff\xd8\xff"

    def test_first_run_seeds_no_alerts(self):
        alert_watcher._events = _frigate_backend(
            [{"id": "a", "label": "person", "camera": "x", "start_time": 100.0}]
        )
        notify.send = lambda *a, **k: self.fail("must not alert on first run")
        notify.send_photo = lambda *a, **k: self.fail("must not alert on first run")
        alert_watcher.main()
        self.assertEqual(float(self.state.read_text()), 100.0)

    def test_retry_hold_on_send_failure(self):
        """Both photo AND text fallback fail → mark must NOT advance."""
        self.state.write_text("50.0")
        alert_watcher._events = _frigate_backend(
            [{"id": "p", "label": "person", "camera": "gate", "start_time": 100.0}]
        )
        alert_watcher._fetch_snapshot = self._no_snapshot
        notify.send = lambda *a, **k: False  # text fallback fails too
        notify.send_photo = lambda *a, **k: False
        alert_watcher.main()
        self.assertEqual(float(self.state.read_text()), 50.0)  # mark held

    def test_pages_through_burst(self):
        self.state.write_text("0.5")
        events = [
            {"id": f"e{i}", "label": "person", "camera": f"c{i}", "start_time": float(i)}
            for i in range(1, 251)
        ]
        alert_watcher._events = _frigate_backend(events)
        alert_watcher._fetch_snapshot = self._no_snapshot
        sent: list = []
        notify.send = lambda t, c=None: (sent.append(t) or True)
        notify.send_photo = lambda *a, **k: False  # force text path
        alert_watcher.main()
        self.assertEqual(len(sent), 250)  # all drained, not truncated to newest 100
        self.assertEqual(float(self.state.read_text()), 250.0)

    def test_corrupt_state_reseeds_loud(self):
        self.state.write_text("garbage")
        alert_watcher._events = _frigate_backend(
            [{"id": "z", "label": "person", "camera": "x", "start_time": 99.0}]
        )
        notify.send = lambda *a, **k: self.fail("must not alert on corrupt re-seed")
        notify.send_photo = lambda *a, **k: self.fail("must not alert on corrupt re-seed")
        alert_watcher.main()
        self.assertEqual(float(self.state.read_text()), 99.0)

    def test_photo_delivered_advances_mark(self):
        """A successful send_photo counts as delivered — mark should advance."""
        self.state.write_text("50.0")
        alert_watcher._events = _frigate_backend(
            [{"id": "q", "label": "car", "camera": "back", "start_time": 200.0}]
        )
        alert_watcher._fetch_snapshot = self._ok_snapshot
        photo_calls: list = []
        notify.send_photo = lambda cap, img, cfg=None: (photo_calls.append(cap) or True)
        notify.send = lambda *a, **k: self.fail("send() must not be called when photo succeeds")
        alert_watcher.main()
        self.assertEqual(len(photo_calls), 1)
        self.assertEqual(float(self.state.read_text()), 200.0)

    def test_photo_fail_text_fallback_advances_mark(self):
        """Photo fetch succeeds but send_photo fails → text fallback → mark advances."""
        self.state.write_text("50.0")
        alert_watcher._events = _frigate_backend(
            [{"id": "r", "label": "person", "camera": "front", "start_time": 300.0}]
        )
        alert_watcher._fetch_snapshot = self._ok_snapshot
        notify.send_photo = lambda *a, **k: False  # photo send fails
        text_calls: list = []
        notify.send = lambda t, c=None: (text_calls.append(t) or True)
        alert_watcher.main()
        self.assertEqual(len(text_calls), 1)
        self.assertEqual(float(self.state.read_text()), 300.0)

    def test_both_fail_holds_mark(self):
        """Both send_photo and text send fail → mark stays at previous value."""
        self.state.write_text("50.0")
        alert_watcher._events = _frigate_backend(
            [{"id": "s", "label": "person", "camera": "side", "start_time": 400.0}]
        )
        alert_watcher._fetch_snapshot = self._ok_snapshot
        notify.send_photo = lambda *a, **k: False
        notify.send = lambda *a, **k: False
        alert_watcher.main()
        self.assertEqual(float(self.state.read_text()), 50.0)  # held


class SitrepTests(unittest.TestCase):
    def test_degrades_when_services_down(self):
        cfg = config.load_config(None)
        cfg["memory_path"] = str(Path(tempfile.mkdtemp()) / "m.jsonl")
        cfg["ollama_url"] = "http://127.0.0.1:5999"
        cfg["sitrep"]["nvr_url"] = "http://127.0.0.1:5999"
        out = sitrep.build_sitrep(cfg)  # no model, no NVR -> raw brief, no crash
        self.assertIn("System", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
