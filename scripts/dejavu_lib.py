"""Shared helpers for DEJA-VU acquisition scripts: safe paths, checksums,
manifest I/O, and human-readable sizes.

Kept dependency-light (stdlib only, `requests` only where actually needed by
callers) so it can be imported directly by the test suite without spinning up
network access or large files.
"""
from __future__ import annotations

import csv
import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

CHUNK_SIZE = 1024 * 1024  # 1 MiB — stream, never load a full file into memory
SUPPORTED_HASH_ALGORITHMS = {"md5", "sha1", "sha256", "sha512"}

_SUB_RE = re.compile(r"sub-(P\d+)", re.IGNORECASE)
_SES_RE = re.compile(r"ses-(S\d+)", re.IGNORECASE)


def parse_participant_session_from_path(path: str) -> dict:
    """Extract BIDS-style `sub-P###` / `ses-S###` tokens from a directory
    path's components. Returns {'subject': str|None, 'session': str|None}.
    """
    subject = None
    session = None
    for part in Path(path).parts:
        if subject is None:
            m = _SUB_RE.search(part)
            if m:
                subject = m.group(1).upper()
        if session is None:
            m = _SES_RE.search(part)
            if m:
                session = m.group(1).upper()
    return {"subject": subject, "session": session}


def parse_participant_session_from_filename(filename: str) -> dict:
    """Extract BIDS-style `sub-P###` / `ses-S###` tokens from a single
    filename (not a full path). Returns {'subject': str|None, 'session': str|None}.
    """
    stem = Path(filename).name
    subject = None
    session = None
    m = _SUB_RE.search(stem)
    if m:
        subject = m.group(1).upper()
    m = _SES_RE.search(stem)
    if m:
        session = m.group(1).upper()
    return {"subject": subject, "session": session}


def identity_conflict(path_identity: dict, filename_identity: dict) -> bool:
    """True if both a path-derived and filename-derived identity are present
    and they disagree on subject and/or session."""
    if path_identity.get("subject") and filename_identity.get("subject"):
        if path_identity["subject"] != filename_identity["subject"]:
            return True
    if path_identity.get("session") and filename_identity.get("session"):
        if path_identity["session"] != filename_identity["session"]:
            return True
    return False


class PathTraversalError(ValueError):
    """Raised when a candidate relative path would escape its base directory."""


def safe_join(base_dir: Path, relative_path: str) -> Path:
    """Join `relative_path` onto `base_dir`, rejecting any path that would
    resolve outside of `base_dir` (absolute paths, `..` escapes, symlink
    tricks are all rejected by resolving and checking containment).
    """
    if not relative_path or relative_path.strip() == "":
        raise PathTraversalError("empty relative path")

    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise PathTraversalError(f"absolute path not allowed: {relative_path!r}")

    base_resolved = base_dir.resolve()
    target_resolved = (base_dir / candidate).resolve()

    try:
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise PathTraversalError(
            f"path {relative_path!r} escapes base directory {base_dir}"
        ) from None

    return target_resolved


def parse_checksum(raw: str) -> tuple[str, str]:
    """Parse a Zenodo-style 'algorithm:hexvalue' checksum string."""
    if not raw or ":" not in raw:
        raise ValueError(f"malformed checksum (expected 'algorithm:value'): {raw!r}")
    algorithm, _, value = raw.partition(":")
    algorithm = algorithm.strip().lower()
    value = value.strip().lower()
    if algorithm not in SUPPORTED_HASH_ALGORITHMS:
        raise ValueError(f"unsupported checksum algorithm: {algorithm!r}")
    if not value or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"malformed checksum value: {value!r}")
    return algorithm, value


def compute_checksum(path: Path, algorithm: str) -> str:
    """Stream `path` through a hashlib digest; never reads the whole file
    into memory at once."""
    if algorithm not in SUPPORTED_HASH_ALGORITHMS:
        raise ValueError(f"unsupported checksum algorithm: {algorithm!r}")
    h = hashlib.new(algorithm)
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@dataclass
class VerifyResult:
    exists: bool
    actual_size_bytes: int | None
    expected_size_bytes: int
    size_match: bool
    checksum_algorithm: str
    expected_checksum: str
    actual_checksum: str | None
    checksum_match: bool

    @property
    def ok(self) -> bool:
        return self.exists and self.size_match and self.checksum_match


def verify_file(path: Path, expected_size: int, checksum_raw: str) -> VerifyResult:
    algorithm, expected_value = parse_checksum(checksum_raw)
    if not path.exists():
        return VerifyResult(
            exists=False,
            actual_size_bytes=None,
            expected_size_bytes=expected_size,
            size_match=False,
            checksum_algorithm=algorithm,
            expected_checksum=expected_value,
            actual_checksum=None,
            checksum_match=False,
        )
    actual_size = path.stat().st_size
    size_match = actual_size == expected_size
    actual_checksum = compute_checksum(path, algorithm)
    checksum_match = actual_checksum == expected_value
    return VerifyResult(
        exists=True,
        actual_size_bytes=actual_size,
        expected_size_bytes=expected_size,
        size_match=size_match,
        checksum_algorithm=algorithm,
        expected_checksum=expected_value,
        actual_checksum=actual_checksum,
        checksum_match=checksum_match,
    )


def human_size(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PiB"


MANIFEST_FIELDNAMES = [
    "record_id", "concept_record_id", "dataset_version", "filename",
    "relative_output_path", "size_bytes", "size_human", "checksum_raw",
    "checksum_algorithm", "checksum_value", "download_url", "media_type",
    "category", "download_status", "local_size_bytes", "checksum_status", "error",
]


def read_manifest(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_manifest_atomic(path: Path, rows: list[dict], fieldnames: list[str] = MANIFEST_FIELDNAMES) -> None:
    """Write the manifest to a temp file in the same directory, then
    atomically rename over the target so a crash mid-write never leaves a
    corrupt manifest."""
    directory = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=".manifest-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k, "") for k in fieldnames})
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


class DirectoryReplaceError(RuntimeError):
    pass


def atomic_directory_replace(current: Path, replacement: Path, backup_name: str) -> Path:
    """Swap `replacement` in as `current`, preserving the prior contents of
    `current` under a sibling directory named `backup_name` (never deleted
    by this function). Mirrors the pattern used to promote a validated
    staging extraction over a partial one.

    Raises DirectoryReplaceError (and makes no change) if:
      - `replacement` does not exist or is empty,
      - a directory already exists at the intended backup path.

    Returns the path `current` now points to (i.e. `current` itself).
    """
    current = Path(current)
    replacement = Path(replacement)
    backup_path = current.parent / backup_name

    if not replacement.is_dir() or not any(replacement.iterdir()):
        raise DirectoryReplaceError(f"replacement directory missing or empty: {replacement}")
    if backup_path.exists():
        raise DirectoryReplaceError(f"backup path already exists, refusing to overwrite: {backup_path}")

    if current.exists():
        os.rename(current, backup_path)
    try:
        os.rename(replacement, current)
    except BaseException:
        # best-effort rollback so we don't leave `current` missing
        if current.exists():
            os.rename(current, replacement)
        if backup_path.exists() and not current.exists():
            os.rename(backup_path, current)
        raise

    return current


_TRAILING_DIGIT_RE = re.compile(r"\s*\d+$")


def normalize_video_name(name: str) -> str:
    """Strip a trailing ' 2'/'3'/... sequel-index suffix, e.g. 'The Shining 2'
    -> 'The Shining'. Does not verify the merged names are actually the same
    content - see docs/dejavu_stimulus_definition_audit.md."""
    return _TRAILING_DIGIT_RE.sub("", name).strip()


def is_rating_midpoint(value: int | float, midpoint: int = 5) -> bool:
    return value == midpoint


def find_duplicate_rating_keys(rows: list[dict], key_fields: list[str]) -> list[tuple]:
    """Given rating rows (dicts), return the list of key tuples that appear
    more than once. Empty list means no duplicates."""
    seen: dict[tuple, int] = {}
    for row in rows:
        key = tuple(row.get(f) for f in key_fields)
        seen[key] = seen.get(key, 0) + 1
    return [key for key, count in seen.items() if count > 1]
