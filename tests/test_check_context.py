import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/context-guard/scripts/check_context.py"
spec = importlib.util.spec_from_file_location("check_context", SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
NOW = datetime(2026, 10, 31, 8, 0, tzinfo=timezone.utc)


def event(tokens=100, window=1000, age=0, **extra):
    info = {"last_token_usage": {"input_tokens": tokens, "cached_input_tokens": tokens,
                                 "output_tokens": 99999, "reasoning_output_tokens": 5000},
            "total_token_usage": {"input_tokens": 99999999}, "model_context_window": window}
    info.update(extra)
    return {"type": "event_msg", "timestamp": (NOW - timedelta(seconds=age)).isoformat(),
            "payload": {"type": "token_count", "info": info}}


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "session.jsonl"

    def write(self, *events, suffix=""):
        self.path.write_text("\n".join(json.dumps(e) for e in events) + suffix, encoding="utf-8")

    def check(self, **kwargs):
        return guard.evaluate(self.path, now=NOW, **kwargs)

    def test_uses_input_not_cumulative_or_cached_subtraction(self):
        self.write(event(100))
        result = self.check()
        self.assertEqual(result["last_input_percent"], 10)
        self.assertFalse(result["should_notify"])

    def test_threshold_boundaries(self):
        for tokens, level, notify in [(349, "normal", False), (350, "watch", True),
                                      (499, "watch", True), (500, "high", True)]:
            with self.subTest(tokens=tokens):
                self.write(event(tokens))
                result = self.check()
                self.assertEqual((result["level"], result["should_notify"]), (level, notify))

    def test_configurable_thresholds(self):
        self.write(event(400))
        self.assertEqual(self.check(warn=30, urgent=40)["level"], "high")

    def test_stale_samples_do_not_alarm(self):
        self.write(event(900, age=601))
        result = self.check()
        self.assertEqual(result["status"], "stale")
        self.assertFalse(result["should_notify"])

    def test_missing_malformed_and_future_timestamps(self):
        for timestamp in [None, "broken", "2026-10-31T08:00:00", "2026-11-01T08:00:00Z"]:
            with self.subTest(timestamp=timestamp):
                e = event(900)
                e["timestamp"] = timestamp
                self.write(e)
                self.assertEqual(self.check()["status"], "unknown")

    def test_partial_json_and_rate_limit_event(self):
        self.write(event(600), {"type": "event_msg", "payload": {"type": "token_count", "info": None}},
                   suffix='\n{"type":"event_msg","payload":{"type":"token_count"')
        self.assertEqual(self.check()["last_input_tokens"], 600)

    def test_unknown_schema_and_bad_counts(self):
        for tokens, window in [(True, 1000), (0, 1000), (-1, 1000), (1, 0), (1001, 1000), (1.5, 1000)]:
            self.write(event(tokens, window))
            self.assertEqual(self.check()["status"], "unknown")
        e = event()
        e["payload"]["info"] = []
        self.write(e)
        self.assertEqual(self.check()["status"], "unknown")

    def test_no_sample_is_unknown(self):
        self.write({"type": "response_item", "content": "sample content"})
        self.assertEqual(self.check()["status"], "unknown")

    def test_ack_suppresses_same_level_and_allows_escalation(self):
        self.write(event(400))
        state_path = self.root / "state.json"
        guard.record_state(state_path, self.check())
        state = guard.read_state(state_path)
        self.assertFalse(self.check(state=state)["should_notify"])
        self.write(event(750))
        self.assertTrue(self.check(state=state)["should_notify"])

    def test_input_drop_and_model_window_change(self):
        self.write(event(400))
        self.assertTrue(self.check(state={"level": "high", "input_tokens": 900})["should_notify"])
        self.write(event(750))
        state = {"level": "high", "input_tokens": 750, "window": 2000}
        self.assertTrue(self.check(state=state)["should_notify"])

    def test_absolute_input_budget_on_large_windows(self):
        for tokens, level in [(127999, "normal"), (128000, "watch"), (192000, "high")]:
            self.write(event(tokens, window=1000000))
            result = self.check()
            self.assertEqual(result["level"], level)
            if level != "normal":
                self.assertIn("input_budget", result["triggered_by"])
        self.assertEqual(self.check(warn_tokens=0, urgent_tokens=0)["level"], "normal")

    def test_fraction_threshold_can_trigger_before_budget(self):
        self.write(event(35000, window=100000))
        self.assertEqual(self.check()["triggered_by"], ["window_fraction"])

    def test_compaction_invalidates_old_sample(self):
        self.write(event(900, age=10), {"type": "compacted", "timestamp": NOW.isoformat()})
        self.assertEqual(self.check()["status"], "stale")

    def test_compaction_rearms_reminder_even_after_regrowth(self):
        self.write(event(900, age=20),
                   {"type": "compacted", "timestamp": (NOW - timedelta(seconds=10)).isoformat()},
                   event(800))
        state = {"level": "high", "input_tokens": 900,
                 "sampled_at": (NOW - timedelta(seconds=20)).isoformat()}
        self.assertTrue(self.check(state=state)["should_notify"])

    def test_bounded_tail(self):
        self.write(event(900))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write("\n" + "x" * (guard.MAX_READ_BYTES + 100))
        self.assertEqual(self.check()["status"], "unknown")

    def test_exact_session_selection_and_ambiguity(self):
        sessions = self.root / "sessions/2026/10/31"
        sessions.mkdir(parents=True)
        mine = sessions / "rollout-mysession123.jsonl"
        mine.touch()
        (sessions / "rollout-other123.jsonl").touch()
        self.assertEqual(guard.locate_session(self.root, "mysession123")[0], mine)
        self.assertIsNone(guard.locate_session(self.root, None)[0])
        self.assertIsNone(guard.locate_session(self.root, "../../bad")[0])
        (sessions / "duplicate-mysession123.jsonl").touch()
        self.assertEqual(guard.locate_session(self.root, "mysession123")[1], "ambiguous_session")

    def test_cli_output_and_state_do_not_contain_transcript(self):
        secret_marker = "PRIVATE_FIXTURE_TEXT_DO_NOT_PRINT"
        e = event(900)
        e["timestamp"] = datetime.now(timezone.utc).isoformat()
        self.write({"type": "response_item", "content": secret_marker}, e)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            guard.main(["--session-file", str(self.path), "--state-dir", str(self.root / "state"), "--record"])
        self.assertNotIn(secret_marker, output.getvalue())
        state = next((self.root / "state").glob("*.json")).read_text()
        self.assertNotIn(secret_marker, state)
        self.assertNotIn(str(self.path), state)

    def test_missing_file_and_corrupt_state(self):
        self.assertEqual(guard.read_state(self.root / "missing"), {})
        self.path.write_text("broken", encoding="utf-8")
        self.assertEqual(guard.read_state(self.path), {})
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            guard.main(["--session-file", str(self.root / "absent")])
        self.assertEqual(json.loads(output.getvalue())["status"], "unknown")

    def test_malformed_reminder_state_is_ignored(self):
        self.write(event(800))
        self.assertTrue(self.check(state={"level": [], "input_tokens": "bad"})["should_notify"])


if __name__ == "__main__":
    unittest.main()
