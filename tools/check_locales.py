#!/usr/bin/env python3
"""Check locale parity and validate each assembled template without third-party packages."""
from contextlib import redirect_stdout
from datetime import date
import importlib.util
import io
import json
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    bootstrap = module("bootstrap", ROOT / "tools/bootstrap.py")
    memory = module("memory", ROOT / "template/scripts/memory.py")
    base = json.loads((ROOT / "template/docs/memory/lessons.json").read_text(encoding="utf-8"))
    fields = ["id", "status", "tags", "path", "reviewed_on", "review_after_days", "superseded_by"]
    base_map = {item["id"]: {key: item[key] for key in fields} for item in base["lessons"]}
    for lang in ["en", "zh-CN"]:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve() / "project"
            with redirect_stdout(io.StringIO()):
                code = bootstrap.install(target, apply=True, lang=lang)
            if code:
                raise ValueError(f"Could not assemble {lang}")
            lessons = memory.load_lessons(target)
            current = {item["id"]: {key: item[key] for key in fields} for item in lessons}
            if current != base_map:
                raise ValueError(f"{lang}: lesson IDs or lifecycle fields drifted")
            errors = memory.validate(target, lessons, date.today())
            if errors:
                raise ValueError(f"{lang}: " + "; ".join(errors))
            print(f"PASS {lang}: {len(lessons)} lessons, matching lifecycle, valid assembled template")


if __name__ == "__main__":
    main()
