#!/usr/bin/env python3
"""Preview or install the starter without overwriting existing project files."""
import argparse
from pathlib import Path
import sys

TEMPLATE = Path(__file__).resolve().parents[1] / "template"


def install(target, apply=False, lang="en"):
    if lang not in {"en", "zh-CN"}:
        raise ValueError("Unsupported language")
    target = Path(target).absolute()
    # Reject symlinked ancestors before resolving, including a not-yet-created target.
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError("Target or an ancestor is a symlink; select the real project path")
    target = target.resolve()
    source = TEMPLATE.resolve()
    if target == source or source in target.parents or target in source.parents:
        raise ValueError("Target overlaps the starter template")
    selected = {}
    layers = [source]
    if lang != "en":
        layers.append(source.parent / "locales" / lang / "template")
    for layer in layers:
        if not layer.is_dir():
            raise ValueError(f"Missing template layer: {lang}")
        for src in sorted(layer.rglob("*")):
            if "__pycache__" in src.parts or src.suffix == ".pyc":
                continue
            if src.is_symlink():
                raise ValueError(f"Template symlink is not supported: {src.name}")
            if src.is_file():
                selected[src.relative_to(layer)] = src
    plan, conflicts = [], []
    for rel, src in sorted(selected.items()):
        dst = target / rel
        if any(p.is_symlink() for p in (dst, *dst.parents)):
            raise ValueError(f"Target symlink is not supported: {rel}")
        data = src.read_bytes()
        if dst.exists():
            if dst.is_file() and dst.read_bytes() == data:
                plan.append(("unchanged", rel, data))
            else:
                conflicts.append(str(rel))
        else:
            # Catch a file occupying a parent directory before any writes.
            if any(p.exists() and not p.is_dir() for p in dst.parents):
                raise ValueError(f"A parent is not a directory: {rel}")
            plan.append(("create", rel, data))
    for action, rel, _ in plan:
        print(f"{action.upper()} {rel.as_posix()}")
    for rel in conflicts:
        print(f"CONFLICT {rel}: preserve existing file; merge manually")
    if conflicts:
        print("No files written. Generate into an empty staging directory, then merge the diff.")
        return 2
    if not apply:
        print("DRY RUN: no files written. Add --apply after reviewing this plan.")
        return 0
    for action, rel, data in plan:
        if action == "create":
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also prevents a concurrently created file being overwritten.
            with dst.open("xb") as stream:
                stream.write(data)
    print("Starter installed. Configure real checks and project memory before declaring readiness.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--lang", choices=["en", "zh-CN"], default="en")
    args = parser.parse_args()
    try:
        return install(args.target, args.apply, args.lang)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
