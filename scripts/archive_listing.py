"""Parse archive member listings from either `lsar -json` (preferred, used
once unar/lsar is installed) or `7z l` (fallback, listing-only — the
DFSG 7zip build can list RAR/RAR5 archives even though it cannot decompress
them).

Kept separate from dejavu_lib.py because it shells out to an external tool;
dejavu_lib.py stays subprocess-free so it can be imported anywhere cheaply.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ArchiveMember:
    raw_path: str  # exactly as stored in the archive, forward slashes
    size_bytes: int
    is_directory: bool
    is_symlink: bool = False


class ArchiveListingError(RuntimeError):
    pass


def _list_with_lsar(archive_path: Path) -> list[ArchiveMember]:
    proc = subprocess.run(
        ["lsar", "-json", str(archive_path)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise ArchiveListingError(f"lsar failed (exit {proc.returncode}): {proc.stderr[:500]}")
    data = json.loads(proc.stdout)
    entries = data.get("lsarContents", [])
    members = []
    for e in entries:
        members.append(ArchiveMember(
            raw_path=e.get("XADFileName", ""),
            size_bytes=int(e.get("XADFileSize", 0) or 0),
            is_directory=bool(e.get("XADIsDirectory", False)),
            is_symlink=bool(e.get("XADIsLink", False) or e.get("XADIsCharacterDevice", False)),
        ))
    return members


_SEVENZ_ROW_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<attr>[.\w]{5})\s+(?P<size>\d+)\s+(?P<compressed>\d*)\s+(?P<name>.+)$"
)


def _list_with_7z(archive_path: Path) -> list[ArchiveMember]:
    proc = subprocess.run(
        ["7z", "l", str(archive_path)],
        capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        raise ArchiveListingError(f"7z l failed (exit {proc.returncode}): {proc.stderr[:500]}")

    members: list[ArchiveMember] = []
    in_table = False
    for line in proc.stdout.splitlines():
        if line.startswith("---"):
            in_table = not in_table
            continue
        if not in_table:
            continue
        m = _SEVENZ_ROW_RE.match(line)
        if not m:
            continue
        attr = m.group("attr")
        members.append(ArchiveMember(
            raw_path=m.group("name"),
            size_bytes=int(m.group("size")),
            is_directory="D" in attr,
            is_symlink=False,  # 7z's `l` output for RAR does not expose link flags reliably
        ))
    return members


def list_archive_members(archive_path: Path) -> tuple[list[ArchiveMember], str]:
    """Returns (members, tool_used)."""
    if shutil.which("lsar"):
        return _list_with_lsar(archive_path), "lsar"
    if shutil.which("7z"):
        return _list_with_7z(archive_path), "7z"
    raise ArchiveListingError("neither lsar nor 7z is available to list archive contents")
