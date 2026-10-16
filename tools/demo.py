#!/usr/bin/env python3
"""Run an offline, disposable demo of honest checks and expiring memory."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location("bootstrap", ROOT / "tools/bootstrap.py")
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    with tempfile.TemporaryDirectory(prefix="agent-starter-demo-") as tmp:
        project = Path(tmp).resolve() / "demo"
        with redirect_stdout(io.StringIO()):
            assert bootstrap.install(project, apply=True) == 0
        print("1. Bootstrap a disposable project (no API keys, installs, or network).")

        def run(*args):
            return subprocess.run([sys.executable, *args], cwd=project, text=True,
                                  encoding="utf-8", capture_output=True, timeout=15)

        empty = run("harness/run.py", "check")
        assert empty.returncode == 2, empty
        print("2. Empty harness -> NOT_CONFIGURED (exit 2), never a fake pass.")
        config = {"schema_version": 1, "projects": [{"name": "demo", "path": ".", "required": ["test"],
                  "checks": {"test": {"commands": [["{python}", "-c", "raise SystemExit(7)"]]}}}]}
        (project / "harness/config.json").write_text(json.dumps(config), encoding="utf-8")
        failed = run("harness/run.py", "check")
        assert failed.returncode == 1, failed
        print("3. Child exits 7 -> harness FAIL (exit 1), failure preserved.")
        config["projects"][0]["checks"]["test"]["commands"] = [["{python}", "-c", "assert 2 + 2 == 4"]]
        (project / "harness/config.json").write_text(json.dumps(config), encoding="utf-8")
        passed = run("harness/run.py", "check")
        assert passed.returncode == 0, passed
        print("4. Passing configured check -> PASS (exit 0). This is a synthetic demo check.")
        registry_path = project / "docs/memory/lessons.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["lessons"][0].update(reviewed_on="2020-01-01", review_after_days=1)
        registry_path.write_text(json.dumps(registry), encoding="utf-8")
        assert run("scripts/memory.py", "index").returncode == 0
        brief = run("scripts/memory.py", "brief", "--task", "memory")
        assert brief.returncode == 0 and "L001" not in brief.stdout
        checked = run("scripts/memory.py", "check")
        assert checked.returncode == 1 and "NEEDS_REVIEW" in checked.stdout
        print("5. Expired lesson -> excluded from brief; check reports NEEDS_REVIEW.")
        print("6. Temporary project removed on exit. Your working files are unchanged.")
    print("Demo passed. Try BOOTSTRAP_PROMPT.md in your own project.")


if __name__ == "__main__":
    main()
