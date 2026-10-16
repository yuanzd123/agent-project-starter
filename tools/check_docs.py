#!/usr/bin/env python3
"""Validate repository-local Markdown and HTML image links; no network requests."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors, count = [], 0
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT)
        # Locale links are validated in the assembled project by check_locales.py.
        if any(part in {".git", ".local", "__pycache__", "locales"} for part in rel.parts):
            continue
        source = path.read_text(encoding="utf-8")
        targets = re.findall(r"\[[^\]]*\]\(([^)]+)\)", source)
        targets += re.findall(r'<(?:img|a)\b[^>]*(?:src|href)="([^"]+)"', source)
        for target in targets:
            parsed = urlsplit(target.strip("<>"))
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            dest = (path.parent / unquote(parsed.path)).resolve()
            count += 1
            if not dest.is_relative_to(ROOT) or not dest.exists():
                errors.append(f"{rel.as_posix()}: invalid local destination {target}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {count} local documentation destinations (external URLs and anchors not checked)")


if __name__ == "__main__":
    main()
