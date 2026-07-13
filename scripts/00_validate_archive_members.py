#!/usr/bin/env python
"""Validate every member of an archive against a safe-extraction policy
BEFORE any extraction is attempted.

Rejects:
  - absolute paths
  - '..' path components
  - paths that would resolve outside the extraction root
  - embedded null characters
  - duplicate normalized paths (exact duplicates after separator normalization)
  - case-collision paths (two distinct paths that would collide on a
    case-insensitive filesystem, e.g. macOS/Windows, even though this
    machine's ext4 filesystem is case-sensitive)
  - symlinks the listing tool flags as such (reported, not silently allowed)

Exit codes:
  0  every member is safe to extract
  1  at least one member failed validation (extraction must not proceed)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive_listing import ArchiveListingError, list_archive_members  # noqa: E402
from dejavu_lib import PathTraversalError, safe_join  # noqa: E402


def validate_members(members, extraction_root: Path) -> list[dict]:
    """Return a list of {member, issue} dicts; empty list means all safe."""
    issues: list[dict] = []
    seen_normalized: dict[str, str] = {}
    seen_casefold: dict[str, str] = {}

    for m in members:
        raw = m.raw_path

        if "\x00" in raw:
            issues.append({"path": raw, "issue": "embedded null character"})
            continue

        if raw.startswith("/") or raw.startswith("\\") or (len(raw) > 1 and raw[1] == ":"):
            issues.append({"path": raw, "issue": "absolute path"})
            continue

        parts = Path(raw.replace("\\", "/")).parts
        if ".." in parts:
            issues.append({"path": raw, "issue": "'..' path component"})
            continue

        try:
            safe_join(extraction_root, raw)
        except PathTraversalError as exc:
            issues.append({"path": raw, "issue": f"escapes extraction root: {exc}"})
            continue

        normalized = "/".join(p for p in raw.replace("\\", "/").split("/") if p not in ("", "."))
        if normalized in seen_normalized:
            issues.append({"path": raw, "issue": f"duplicate normalized path (also: {seen_normalized[normalized]!r})"})
        else:
            seen_normalized[normalized] = raw

        folded = normalized.casefold()
        if folded in seen_casefold and seen_casefold[folded] != normalized:
            issues.append({
                "path": raw,
                "issue": f"case-collision with {seen_casefold[folded]!r} (would collide on a case-insensitive filesystem)",
            })
        else:
            seen_casefold.setdefault(folded, normalized)

        if m.is_symlink:
            issues.append({"path": raw, "issue": "symlink member (rejected — not extracted verbatim without manual review)"})

    return issues


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: 00_validate_archive_members.py <archive_path> <extraction_root>", file=sys.stderr)
        return 2

    archive_path = Path(sys.argv[1])
    extraction_root = Path(sys.argv[2])
    extraction_root.mkdir(parents=True, exist_ok=True)

    try:
        members, tool = list_archive_members(archive_path)
    except ArchiveListingError as exc:
        print(f"FAILED to list archive: {exc}", file=sys.stderr)
        return 1

    file_members = [m for m in members if not m.is_directory]
    dir_members = [m for m in members if m.is_directory]
    print(f"listed {len(members)} members ({len(file_members)} files, {len(dir_members)} dirs) via {tool}")

    issues = validate_members(members, extraction_root)
    if issues:
        print(f"VALIDATION FAILED: {len(issues)} issue(s)", file=sys.stderr)
        for i in issues:
            print(f"  - {i['path']!r}: {i['issue']}", file=sys.stderr)
        return 1

    print("VALIDATION PASSED: no path traversal, no absolute paths, no null bytes, "
          "no duplicate/case-colliding paths, no symlinks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
