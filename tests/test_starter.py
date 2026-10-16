import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


memory = load("memory_tool", ROOT / "template/scripts/memory.py")


class StarterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.repo = self.base / "project with spaces"
        shutil.copytree(ROOT / "template", self.repo, ignore=shutil.ignore_patterns("__pycache__"))

    def run_tool(self, path, *args, cwd=None):
        return subprocess.run([sys.executable, str(path), *map(str, args)], cwd=cwd or self.base,
                              text=True, encoding="utf-8", capture_output=True, timeout=15)

    def harness(self, *args):
        return self.run_tool(self.repo / "harness/run.py", *args)

    def configure(self, commands, path=".", required=None):
        data = {"schema_version": 1, "projects": [{"name": "app", "path": path,
                "required": required or ["test"], "checks": {"test": {"commands": commands}}}]}
        (self.repo / "harness/config.json").write_text(json.dumps(data), encoding="utf-8")
        return data

    def save_registry(self, lessons):
        (self.repo / "docs/memory/lessons.json").write_text(
            json.dumps({"schema_version": 1, "lessons": lessons}), encoding="utf-8")

    def test_empty_app_is_not_reported_as_passing(self):
        result = self.harness("check")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("NOT_CONFIGURED", result.stderr)
        self.assertNotIn("PASS", result.stdout)

    def test_failure_stops_later_command_and_is_nonzero(self):
        self.configure([["{python}", "-c", "raise SystemExit(7)"],
                        ["{python}", "-c", "open('should-not-exist','w').write('bad')"]])
        result = self.harness("test")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse((self.repo / "should-not-exist").exists())
        self.assertNotIn("PASS", result.stdout)

    def test_runs_in_registered_project_from_unrelated_cwd(self):
        child = self.repo / "apps" / "nested app"
        child.mkdir(parents=True)
        (child / "marker").write_text("correct", encoding="utf-8")
        self.configure([["{python}", "-c", "from pathlib import Path; assert Path('marker').read_text() == 'correct'"]],
                       path="apps/nested app")
        result = self.harness("test")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_required_check_fails_before_running_any(self):
        self.configure([["{python}", "-c", "open('should-not-exist','w').write('bad')"]],
                       required=["test", "build"])
        result = self.harness("check")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.repo / "should-not-exist").exists())

    def test_dry_run_has_no_side_effects(self):
        self.configure([["{python}", "-c", "open('should-not-exist','w').write('bad')"]])
        result = self.harness("check", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertFalse((self.repo / "should-not-exist").exists())

    def test_unknown_project_and_escaped_path_rejected(self):
        self.configure([["{python}", "-c", "pass"]])
        self.assertEqual(self.harness("test", "--project", "unknown").returncode, 2)
        self.configure([["{python}", "-c", "pass"]], path="..")
        self.assertEqual(self.harness("test").returncode, 2)

    def test_missing_executable_is_unavailable(self):
        self.configure([["nonexistent-starter-test-executable"]])
        result = self.harness("test")
        self.assertEqual(result.returncode, 2)
        self.assertIn("NOT_AVAILABLE", result.stderr)

    def test_timeout_is_failure(self):
        data = self.configure([["{python}", "-c", "import time; time.sleep(5)"]])
        data["projects"][0]["checks"]["test"]["timeout_seconds"] = 0.05
        (self.repo / "harness/config.json").write_text(json.dumps(data), encoding="utf-8")
        result = self.harness("test")
        self.assertEqual(result.returncode, 1)
        self.assertIn("timed out", result.stderr)

    def test_check_includes_memory_validation(self):
        self.configure([["{python}", "-c", "pass"]])
        (self.repo / "docs/memory/LESSONS_INDEX.md").write_text("drift", encoding="utf-8")
        result = self.harness("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("index drift", result.stdout)

    def test_memory_baseline_and_generated_index(self):
        lessons = memory.load_lessons(self.repo)
        self.assertEqual(memory.validate(self.repo, lessons, date(2026, 10, 15)), [])
        result = self.run_tool(self.repo / "scripts/memory.py", "brief", "--task", "database", "--as-of", "2026-10-15")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("L010", result.stdout)
        self.assertNotIn("L903", result.stdout)

    def test_expired_candidate_and_retired_lessons_excluded(self):
        lessons = memory.load_lessons(self.repo)
        lessons[0]["review_after_days"] = 1
        result = memory.brief(lessons, "always memory toolchain", date(2026, 10, 16), limit=50)
        for ident in ("L001", "L901", "L902", "L903", "L990", "L991"):
            self.assertNotIn(ident, result)
        self.assertTrue(any("NEEDS_REVIEW" in e for e in memory.validate(self.repo, lessons, date(2026, 10, 16))))

    def test_duplicate_id_and_replacement_cycle_rejected(self):
        lessons = memory.load_lessons(self.repo)
        lessons[1]["id"] = lessons[0]["id"]
        self.save_registry(lessons)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            memory.load_lessons(self.repo)
        lessons[1]["id"] = "L002"
        lessons[0]["superseded_by"] = "L002"
        lessons[1]["superseded_by"] = "L001"
        self.save_registry(lessons)
        with self.assertRaisesRegex(ValueError, "cyclic"):
            memory.load_lessons(self.repo)

    def test_unregistered_file_and_broken_link_detected(self):
        lessons = memory.load_lessons(self.repo)
        extra = self.repo / "docs/memory/lessons/extra.md"
        extra.write_text("orphan", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cover exactly"):
            memory.load_lessons(self.repo)
        extra.unlink()
        with (self.repo / "docs/memory/MEMORY.md").open("a", encoding="utf-8") as stream:
            stream.write("\n[missing](does-not-exist.md)\n")
        self.assertTrue(any("missing or external" in e for e in memory.validate(self.repo, lessons, date(2026, 10, 15))))

    def test_brief_budget_and_scope(self):
        lessons = memory.load_lessons(self.repo)
        result = memory.brief(lessons, "ui", date(2026, 10, 15), limit=2, budget=500)
        self.assertLessEqual(len(result), 500)
        self.assertIn("L012", result)
        self.assertNotIn("L010", result)

    def test_bootstrap_preview_then_idempotent_apply(self):
        target = self.base / "new project"
        tool = ROOT / "tools/bootstrap.py"
        result = self.run_tool(tool, target)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(target.exists())
        first = self.run_tool(tool, target, "--apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        files = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
        second = self.run_tool(tool, target, "--apply")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn("CREATE ", second.stdout)
        self.assertEqual(files, {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()})

    def test_bootstrap_conflict_writes_nothing(self):
        target = self.base / "existing project"
        target.mkdir()
        (target / "AGENTS.md").write_text("user instructions", encoding="utf-8")
        result = self.run_tool(ROOT / "tools/bootstrap.py", target, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(target.iterdir()), [target / "AGENTS.md"])
        self.assertEqual((target / "AGENTS.md").read_text(), "user instructions")

    def test_bootstrap_rejects_symlink_escape(self):
        target = self.base / "linked project"
        target.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        try:
            (target / "docs").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symlinks is unavailable on this host")
        result = self.run_tool(ROOT / "tools/bootstrap.py", target, "--apply")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(list(outside.iterdir()), [])

    def test_chinese_install_keeps_runtime_and_localizes_memory(self):
        target = self.base / "Chinese project"
        result = self.run_tool(ROOT / "tools/bootstrap.py", target, "--lang", "zh-CN", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        registry = json.loads((target / "docs/memory/lessons.json").read_text(encoding="utf-8"))
        self.assertIn("权威", registry["lessons"][0]["title"])
        self.assertEqual((target / "scripts/memory.py").read_bytes(), (ROOT / "template/scripts/memory.py").read_bytes())
        checked = self.run_tool(target / "scripts/memory.py", "check", "--as-of", "2026-10-15")
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)


if __name__ == "__main__":
    unittest.main()
