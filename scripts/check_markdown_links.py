#!/usr/bin/env python3
"""Validate local markdown links and anchors.

Checks:
- Relative file links exist.
- Optional file anchors (#heading) exist in target markdown files.

Skips:
- http/https links
- mailto links
- in-page anchors (#...)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")


def _slugify_heading(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def _collect_headings(path: Path) -> set[str]:
    headings: set[str] = set()
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return headings

    for line in content.splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        headings.add(_slugify_heading(match.group(1)))
    return headings


def _iter_links(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return []
    return [target for _label, target in LINK_RE.findall(text)]


def _validate_link(source: Path, target: str) -> list[str]:
    errors: list[str] = []

    if target.startswith(("http://", "https://", "mailto:")):
        return errors
    if target.startswith("#"):
        return errors

    target = unquote(target)
    file_part, _, anchor = target.partition("#")
    candidate = (source.parent / file_part).resolve()

    if not candidate.exists():
        errors.append(f"{source}: missing link target '{target}'")
        return errors

    if anchor and candidate.suffix.lower() == ".md":
        headings = _collect_headings(candidate)
        if anchor not in headings:
            errors.append(
                f"{source}: missing anchor '#{anchor}' in '{candidate.relative_to(Path.cwd())}'"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="Markdown files to check")
    args = parser.parse_args()

    all_errors: list[str] = []
    for filename in args.files:
        source = Path(filename).resolve()
        for target in _iter_links(source):
            all_errors.extend(_validate_link(source, target))

    if all_errors:
        print("Markdown link validation failed:")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("Markdown link validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
