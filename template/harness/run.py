#!/usr/bin/env python3
"""Explicit, fail-closed project checks. No dependency install or deployment side effects."""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STAGES = {"lint", "typecheck", "test", "build"}


def load_config(root):
    config = json.loads((root / "harness/config.json").read_text(encoding="utf-8"))
    if config.get("schema_version") != 1 or not isinstance(config.get("projects"), list):
        raise ValueError("Expected schema_version=1 and projects array")
    seen = set()
    for project in config["projects"]:
        if not isinstance(project, dict):
            raise ValueError("Each project must be an object")
        name = project.get("name")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("Project names must be nonempty and unique")
        seen.add(name)
        path = project.get("path")
        if not isinstance(path, str) or Path(path).is_absolute():
            raise ValueError(f"{name}: path must be repository-relative")
        cwd = (root / path).resolve()
        if not cwd.is_relative_to(root) or not cwd.is_dir():
            raise ValueError(f"{name}: path escapes repository or does not exist")
        required = project.get("required")
        checks = project.get("checks")
        if not isinstance(required, list) or not required or not all(isinstance(s, str) for s in required) or len(set(required)) != len(required):
            raise ValueError(f"{name}: required must contain distinct stages")
        if not isinstance(checks, dict) or not set(required) <= STAGES or not set(checks) <= STAGES:
            raise ValueError(f"{name}: invalid stages/checks")
        for stage, spec in checks.items():
            if not isinstance(spec, dict):
                raise ValueError(f"{name}/{stage}: expected a check object")
            commands = spec.get("commands")
            if not isinstance(commands, list) or not commands:
                raise ValueError(f"{name}/{stage}: commands must be a nonempty array")
            for command in commands:
                if not isinstance(command, list) or not command or not all(isinstance(a, str) and a and "\x00" not in a for a in command):
                    raise ValueError(f"{name}/{stage}: use argv arrays, not shell strings")
            timeout = spec.get("timeout_seconds", 300)
            if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError(f"{name}/{stage}: timeout must be positive and finite")
    return config


def execute(argv, cwd, timeout):
    argv = [sys.executable if arg == "{python}" else arg for arg in argv]
    try:
        result = subprocess.run(argv, cwd=cwd, timeout=timeout, check=False)
    except FileNotFoundError:
        print("NOT_AVAILABLE: executable not found", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("FAIL: command timed out", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"FAIL: could not launch command ({type(exc).__name__})", file=sys.stderr)
        return 1
    return 0 if result.returncode == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["list", "check", *sorted(STAGES)])
    parser.add_argument("--project", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        config = load_config(ROOT)
        projects = config["projects"]
        names = {p["name"] for p in projects}
        if set(args.project) - names:
            raise ValueError("Unknown project selector")
        selected = [p for p in projects if not args.project or p["name"] in args.project]
        if args.stage == "list":
            for p in selected:
                print(f"{p['name']}: {p['path']} | required={','.join(p['required'])}")
            if not selected:
                print("NOT_CONFIGURED: no application projects")
            return 0
        # Validate the complete selected plan before running even the first command.
        if not selected:
            raise ValueError("NOT_CONFIGURED: register actual projects and required checks first")
        plan = []
        for p in selected:
            stages = p["required"] if args.stage == "check" else [args.stage]
            for stage in stages:
                if stage not in p["checks"]:
                    raise ValueError(f"NOT_CONFIGURED: {p['name']}/{stage}")
                spec = p["checks"][stage]
                for argv in spec["commands"]:
                    plan.append((f"{p['name']}/{stage}", (ROOT / p["path"]).resolve(), argv, spec.get("timeout_seconds", 300)))
        if args.stage == "check":
            plan.insert(0, ("memory", ROOT, ["{python}", "scripts/memory.py", "check"], 30))
        for label, cwd, argv, timeout in plan:
            # Do not echo command arguments: commands must use env names, never secret values.
            print(f"{'PLAN' if args.dry_run else 'RUN'} {label} cwd={cwd.relative_to(ROOT)}", flush=True)
            if not args.dry_run:
                code = execute(argv, cwd, timeout)
                if code:
                    print(f"FAIL {label}", file=sys.stderr)
                    return code
        print("DRY RUN: nothing executed" if args.dry_run else "PASS: selected configured checks")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
