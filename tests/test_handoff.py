import contextlib
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "skills/context-guard/scripts/handoff.py"
spec = importlib.util.spec_from_file_location("handoff", SCRIPT)
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project with spaces"
        self.project.mkdir()
        self.data = {key: "Not applicable for this test." for key in handoff.FIELDS}
        self.data.update(goal="修订视频文稿，保留数字和条件。", next_action="核实输出文件，再检查第一段。")

    def create(self, **kwargs):
        return handoff.create(self.project, "字幕交接", self.data, **kwargs)

    def test_complete_chinese_roundtrip(self):
        result = self.create()
        path = Path(result["path"])
        meta, fields = handoff.parse(path.read_text(encoding="utf-8"))
        self.assertEqual(fields["goal"], self.data["goal"])
        self.assertEqual(meta["project"], str(self.project.resolve()))
        self.assertTrue(result["validation"]["valid"])
        self.assertFalse(meta["snapshot"]["git"])

    def test_draft_is_not_ready_to_resume(self):
        result = handoff.create(self.project, "Draft")
        self.assertTrue(result["draft"])
        self.assertFalse(result["validation"]["valid"])

    def test_creates_exclusively(self):
        first = self.create()
        second = self.create()
        self.assertNotEqual(first["path"], second["path"])
        self.assertTrue(Path(first["path"]).exists())

    def test_non_git_with_no_baseline_requires_review(self):
        path = Path(self.create()["path"])
        self.assertEqual(handoff.check(path)["status"], "review")

    def test_changed_and_missing_artifact(self):
        artifact = self.project / "输出.txt"
        artifact.write_text("first", encoding="utf-8")
        path = Path(self.create(files=[artifact.name])["path"])
        self.assertEqual(handoff.check(path)["status"], "fresh")
        artifact.write_text("other", encoding="utf-8")
        self.assertEqual(handoff.check(path)["status"], "stale")
        artifact.unlink()
        self.assertEqual(handoff.check(path)["status"], "stale")

    def test_path_escape_and_nonexistent_project(self):
        outside = self.project.parent / "outside.txt"
        outside.write_text("local fixture", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.create(files=["../outside.txt"])
        with self.assertRaises(ValueError):
            handoff.create(self.project / "missing", "bad")
        self.assertFalse((self.project / ".codex").exists())

    def test_secrets_are_rejected_before_writing(self):
        markers = ["ghp_" + "a" * 30, "-----BEGIN PRIVATE KEY-----", "password: secretvalue123"]
        for marker in markers:
            with self.subTest(marker=marker[:8]):
                self.data["pending"] = marker
                with self.assertRaises(ValueError):
                    self.create()
        self.assertFalse((self.project / ".codex").exists())

    def test_missing_fields_and_placeholders_rejected(self):
        with self.assertRaises(ValueError):
            handoff.create(self.project, "bad", {"goal": "only goal"})
        self.data["next_action"] = "[TODO: replace me]"
        with self.assertRaises(ValueError):
            self.create()

    def test_lineage_is_a_pointer_not_recursive_import(self):
        first = Path(self.create()["path"])
        second = Path(self.create(previous=first)["path"])
        meta, _ = handoff.parse(second.read_text(encoding="utf-8"))
        self.assertEqual(meta["continues_from"], first.name)
        self.assertLess(second.stat().st_size, first.stat().st_size * 1.5)
        with self.assertRaises(ValueError):
            self.create(previous=self.project.parent / "not-a-handoff.md")

    def test_old_or_mismatched_project_requires_review(self):
        path = Path(self.create()["path"])
        future = datetime.now(timezone.utc) + timedelta(days=2)
        self.assertIn("age_requires_review", handoff.check(path, now=future)["reasons"])
        self.assertEqual(handoff.check(path, project=self.project.parent)["status"], "stale")

    def test_git_branch_head_dirty_and_self_exclusion(self):
        def git(*args):
            return subprocess.run(["git", *args], cwd=self.project, capture_output=True, check=True)
        git("init", "-b", "main")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.invalid")
        file = self.project / "file.txt"
        file.write_text("initial", encoding="utf-8")
        git("add", "file.txt")
        git("commit", "-m", "fixture")
        path = Path(self.create(files=["file.txt"])["path"])
        self.assertEqual(handoff.check(path)["status"], "fresh")
        file.write_text("changed", encoding="utf-8")
        self.assertEqual(handoff.check(path)["status"], "stale")
        git("checkout", "-b", "other")
        self.assertIn("git_branch_changed", handoff.check(path)["reasons"])

    def test_list_and_resume_cli(self):
        path = Path(self.create()["path"])
        rows = handoff.list_handoffs(self.project)
        self.assertEqual(rows[0]["path"], str(path))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = handoff.main(["resume", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["next_action"], self.data["next_action"])

    def test_invalid_cli_does_not_echo_input(self):
        path = self.project / "broken.md"
        marker = "ghp_" + "b" * 30
        path.write_text(marker, encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = handoff.main(["resume", str(path)])
        self.assertEqual(code, 1)
        self.assertNotIn(marker, output.getvalue())

    def test_large_document_and_unknown_metadata(self):
        path = self.project / "large.md"
        path.write_text("a" * (handoff.MAX_DOCUMENT + 1), encoding="utf-8")
        with self.assertRaises(ValueError):
            handoff.read_document(path)
        self.assertFalse(handoff.validate_text("No metadata")["valid"])


if __name__ == "__main__":
    unittest.main()
