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
import frigate as frigate_mod  # noqa: E402
import memory  # noqa: E402
import notify  # noqa: E402
import sitrep  # noqa: E402
import telegram_bot  # noqa: E402


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

    def be(nvr_url, after, before=None, api_key=""):
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

    def test_nvr_api_key_default_empty(self):
        cfg = config.load_config(None)
        self.assertEqual(cfg["sitrep"]["nvr_api_key"], "")

    def test_alerts_cooldown_default(self):
        cfg = config.load_config(None)
        self.assertEqual(cfg["alerts"]["cooldown_seconds"], 120)

    def test_alerts_deep_merged(self):
        p = str(Path(tempfile.mkdtemp()) / "c.json")
        Path(p).write_text(json.dumps({"alerts": {"cooldown_seconds": 30}}))
        cfg = config.load_config(p)
        self.assertEqual(cfg["alerts"]["cooldown_seconds"], 30)


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


class FrigateAuthTests(unittest.TestCase):
    """FIX 1: Frigate API key header injection tests."""

    def test_no_key_no_auth_header(self):
        """When no API key is configured, no Authorization header is added."""
        req = frigate_mod.frigate_get("http://localhost:5000/api/events", api_key="")
        self.assertIsNone(req.get_header("Authorization"))

    def test_key_adds_bearer_header(self):
        """When an API key is set, Authorization: Bearer <key> is present."""
        req = frigate_mod.frigate_get(
            "http://localhost:5000/api/events", api_key="secret123"
        )
        self.assertEqual(req.get_header("Authorization"), "Bearer secret123")

    def test_env_key_wins_over_config(self):
        """FRIGATE_API_KEY env var takes priority over config file value."""
        import os

        orig = os.environ.get("FRIGATE_API_KEY")
        try:
            os.environ["FRIGATE_API_KEY"] = "env-key"
            cfg = {"sitrep": {"nvr_api_key": "cfg-key"}}
            self.assertEqual(frigate_mod.get_api_key(cfg), "env-key")
        finally:
            if orig is None:
                os.environ.pop("FRIGATE_API_KEY", None)
            else:
                os.environ["FRIGATE_API_KEY"] = orig

    def test_config_key_used_when_no_env(self):
        """Config file value is used when FRIGATE_API_KEY env var is absent."""
        import os

        orig = os.environ.get("FRIGATE_API_KEY")
        try:
            os.environ.pop("FRIGATE_API_KEY", None)
            cfg = {"sitrep": {"nvr_api_key": "cfg-only"}}
            self.assertEqual(frigate_mod.get_api_key(cfg), "cfg-only")
        finally:
            if orig is not None:
                os.environ["FRIGATE_API_KEY"] = orig

    def test_no_key_config_returns_empty(self):
        """get_api_key returns '' when neither env nor config supplies a key."""
        import os

        orig = os.environ.get("FRIGATE_API_KEY")
        try:
            os.environ.pop("FRIGATE_API_KEY", None)
            cfg = config.load_config(None)
            self.assertEqual(frigate_mod.get_api_key(cfg), "")
        finally:
            if orig is not None:
                os.environ["FRIGATE_API_KEY"] = orig

    def test_fetch_json_sends_auth_header(self):
        """fetch_json passes the Bearer header through to the actual request."""
        captured_headers: list[str] = []

        def fake_urlopen(req, timeout=0):
            auth = req.get_header("Authorization")
            if auth:
                captured_headers.append(auth)
            return _Resp(b'[{"label":"person"}]')

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            result = frigate_mod.fetch_json(
                "http://localhost:5000/api/events", api_key="mykey", timeout=5
            )
        finally:
            urllib.request.urlopen = orig

        self.assertEqual(result, [{"label": "person"}])
        self.assertEqual(captured_headers, ["Bearer mykey"])

    def test_fetch_json_no_header_without_key(self):
        """fetch_json sends no Authorization header when api_key is empty."""
        captured_headers: list[str] = []

        def fake_urlopen(req, timeout=0):
            auth = req.get_header("Authorization")
            captured_headers.append(auth)
            return _Resp(b'[]')

        orig = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            frigate_mod.fetch_json(
                "http://localhost:5000/api/events", api_key="", timeout=5
            )
        finally:
            urllib.request.urlopen = orig

        self.assertEqual(captured_headers, [None])


class TelegramBotTests(unittest.TestCase):
    """FIX 2: should_handle authz + backoff helpers."""

    # --- should_handle ---

    def test_should_handle_correct_chat_with_text(self):
        upd = {"message": {"chat": {"id": 42}, "text": "hello"}}
        self.assertTrue(telegram_bot.should_handle(upd, "42"))

    def test_should_handle_wrong_chat_id(self):
        """Security check: different chat id -> False."""
        upd = {"message": {"chat": {"id": 99}, "text": "hello"}}
        self.assertFalse(telegram_bot.should_handle(upd, "42"))

    def test_should_handle_empty_text(self):
        upd = {"message": {"chat": {"id": 42}, "text": ""}}
        self.assertFalse(telegram_bot.should_handle(upd, "42"))

    def test_should_handle_no_message_key(self):
        upd = {"update_id": 1}
        self.assertFalse(telegram_bot.should_handle(upd, "42"))

    def test_should_handle_no_text_key(self):
        upd = {"message": {"chat": {"id": 42}}}
        self.assertFalse(telegram_bot.should_handle(upd, "42"))

    def test_should_handle_edited_message(self):
        """edited_message is also accepted when chat id + text match."""
        upd = {"edited_message": {"chat": {"id": 7}, "text": "edit"}}
        self.assertTrue(telegram_bot.should_handle(upd, "7"))

    # --- _next_backoff ---

    def test_backoff_first_delay_is_base(self):
        self.assertEqual(telegram_bot._next_backoff(0, base=1, cap=60), 1)

    def test_backoff_doubles_each_step(self):
        b = 1.0
        delays = []
        for _ in range(4):
            b = telegram_bot._next_backoff(b, base=1, cap=60)
            delays.append(b)
        # 1 -> 2 -> 4 -> 8 (first call from 0 gives 1; subsequent double)
        self.assertEqual(delays, [2.0, 4.0, 8.0, 16.0])

    def test_backoff_caps_at_cap(self):
        b = telegram_bot._next_backoff(50, base=1, cap=60)
        self.assertEqual(b, 60)
        b = telegram_bot._next_backoff(60, base=1, cap=60)
        self.assertEqual(b, 60)

    def test_backoff_reset_to_zero_means_no_initial_sleep(self):
        """After reset to 0, _next_backoff gives base (not 0)."""
        self.assertEqual(telegram_bot._next_backoff(0, base=1, cap=60), 1)


class AlertWatcherTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.state = self.tmpdir / "aw.state"
        self.cooldown_state = self.tmpdir / "aw.cooldown.json"
        self._orig_state = alert_watcher.STATE
        self._orig_cooldown_state = alert_watcher.COOLDOWN_STATE
        self._orig_events = alert_watcher._events
        self._orig_send = notify.send
        self._orig_send_photo = notify.send_photo
        self._orig_fetch_snapshot = alert_watcher._fetch_snapshot
        alert_watcher.STATE = self.state
        alert_watcher.COOLDOWN_STATE = self.cooldown_state
        sys.argv = ["alert_watcher.py", "--config", "/nonexistent.json"]

    def tearDown(self):
        alert_watcher.STATE = self._orig_state
        alert_watcher.COOLDOWN_STATE = self._orig_cooldown_state
        alert_watcher._events = self._orig_events
        notify.send = self._orig_send
        notify.send_photo = self._orig_send_photo
        alert_watcher._fetch_snapshot = self._orig_fetch_snapshot

    def _no_snapshot(self, nvr_url: str, event_id: str, api_key: str = "") -> None:
        """Stub: snapshot unavailable (None) so alerts fall back to text."""
        return None

    def _ok_snapshot(self, nvr_url: str, event_id: str, api_key: str = "") -> bytes:
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

    # --- FIX 3: cooldown tests ---

    def test_cooldown_suppresses_second_alert_same_camera(self):
        """Two events on same camera within cooldown: only ONE message sent,
        but BOTH advance the mark (no retry on the suppressed one)."""
        self.state.write_text("0.0")
        # Both events at t=10 and t=20, cooldown=120 — second is suppressed.
        events = [
            {"id": "e1", "label": "person", "camera": "gate", "start_time": 10.0},
            {"id": "e2", "label": "person", "camera": "gate", "start_time": 20.0},
        ]
        alert_watcher._events = _frigate_backend(events)
        alert_watcher._fetch_snapshot = self._no_snapshot
        sent: list = []
        notify.send = lambda t, c=None: (sent.append(t) or True)
        notify.send_photo = lambda *a, **k: False
        alert_watcher.main()
        # Only one alert fired
        self.assertEqual(len(sent), 1)
        # Mark advances past BOTH events (suppressed event is not retried)
        self.assertEqual(float(self.state.read_text()), 20.0)

    def test_cooldown_different_cameras_both_alert(self):
        """Two events on DIFFERENT cameras within cooldown: BOTH alert."""
        self.state.write_text("0.0")
        events = [
            {"id": "e1", "label": "person", "camera": "front", "start_time": 10.0},
            {"id": "e2", "label": "person", "camera": "back", "start_time": 15.0},
        ]
        alert_watcher._events = _frigate_backend(events)
        alert_watcher._fetch_snapshot = self._no_snapshot
        sent: list = []
        notify.send = lambda t, c=None: (sent.append(t) or True)
        notify.send_photo = lambda *a, **k: False
        alert_watcher.main()
        self.assertEqual(len(sent), 2)
        self.assertEqual(float(self.state.read_text()), 15.0)

    def test_cooldown_expired_alerts_again(self):
        """An event past the cooldown window alerts again."""
        # Seed the cooldown state: camera "gate" last delivered at t=10
        self.cooldown_state.parent.mkdir(parents=True, exist_ok=True)
        self.cooldown_state.write_text(json.dumps({"gate": 10.0}))
        self.state.write_text("10.0")
        # New event at t=200 (well beyond default 120s cooldown from t=10)
        events = [
            {"id": "e3", "label": "person", "camera": "gate", "start_time": 200.0},
        ]
        alert_watcher._events = _frigate_backend(events)
        alert_watcher._fetch_snapshot = self._no_snapshot
        sent: list = []
        notify.send = lambda t, c=None: (sent.append(t) or True)
        notify.send_photo = lambda *a, **k: False
        alert_watcher.main()
        self.assertEqual(len(sent), 1)
        self.assertEqual(float(self.state.read_text()), 200.0)

    def test_cooldown_delivery_failure_does_not_advance_mark(self):
        """Cooldown suppressed=advance mark; delivery failure=hold mark — not conflated."""
        self.state.write_text("0.0")
        # e1 fails delivery; e2 is on a different camera and would be in-window,
        # but we never reach it because stop=True after e1 failure.
        events = [
            {"id": "e1", "label": "person", "camera": "gate", "start_time": 10.0},
        ]
        alert_watcher._events = _frigate_backend(events)
        alert_watcher._fetch_snapshot = self._no_snapshot
        notify.send = lambda *a, **k: False
        notify.send_photo = lambda *a, **k: False
        alert_watcher.main()
        # Mark must be held at 0.0 — delivery failed
        self.assertEqual(float(self.state.read_text()), 0.0)


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
