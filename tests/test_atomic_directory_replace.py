"""Tests for dejavu_lib.atomic_directory_replace — the safe swap-in pattern
used to promote a validated unrar staging extraction over a partial unar one."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pytest  # noqa: E402
from dejavu_lib import DirectoryReplaceError, atomic_directory_replace  # noqa: E402


def make_dir_with_file(path: Path, filename: str, content: bytes) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / filename).write_bytes(content)


def test_swap_replaces_current_and_preserves_backup(tmp_path):
    current = tmp_path / "dataset"
    replacement = tmp_path / "dataset_staging"
    make_dir_with_file(current, "old.txt", b"partial data")
    make_dir_with_file(replacement, "new.txt", b"complete data")

    result = atomic_directory_replace(current, replacement, "dataset_partial_backup")

    assert result == current
    assert (current / "new.txt").read_bytes() == b"complete data"
    assert not (current / "old.txt").exists()
    backup = tmp_path / "dataset_partial_backup"
    assert backup.is_dir()
    assert (backup / "old.txt").read_bytes() == b"partial data"


def test_backup_is_never_deleted(tmp_path):
    current = tmp_path / "dataset"
    replacement = tmp_path / "dataset_staging"
    make_dir_with_file(current, "old.txt", b"x")
    make_dir_with_file(replacement, "new.txt", b"y")

    atomic_directory_replace(current, replacement, "backup")

    assert (tmp_path / "backup").exists()
    assert (tmp_path / "backup" / "old.txt").exists()


def test_refuses_empty_replacement(tmp_path):
    current = tmp_path / "dataset"
    replacement = tmp_path / "dataset_staging"
    make_dir_with_file(current, "old.txt", b"x")
    replacement.mkdir()  # empty, no files

    with pytest.raises(DirectoryReplaceError):
        atomic_directory_replace(current, replacement, "backup")

    # current must be untouched
    assert (current / "old.txt").exists()


def test_refuses_missing_replacement(tmp_path):
    current = tmp_path / "dataset"
    make_dir_with_file(current, "old.txt", b"x")

    with pytest.raises(DirectoryReplaceError):
        atomic_directory_replace(current, tmp_path / "does_not_exist", "backup")


def test_refuses_if_backup_name_already_taken(tmp_path):
    current = tmp_path / "dataset"
    replacement = tmp_path / "dataset_staging"
    make_dir_with_file(current, "old.txt", b"x")
    make_dir_with_file(replacement, "new.txt", b"y")
    make_dir_with_file(tmp_path / "backup", "preexisting.txt", b"do not touch")

    with pytest.raises(DirectoryReplaceError):
        atomic_directory_replace(current, replacement, "backup")

    # neither current nor the pre-existing backup should be modified
    assert (current / "old.txt").exists()
    assert (tmp_path / "backup" / "preexisting.txt").read_bytes() == b"do not touch"


def test_swap_works_when_current_does_not_yet_exist(tmp_path):
    replacement = tmp_path / "dataset_staging"
    make_dir_with_file(replacement, "new.txt", b"first extraction")

    result = atomic_directory_replace(tmp_path / "dataset", replacement, "backup")

    assert (result / "new.txt").read_bytes() == b"first extraction"
    assert not (tmp_path / "backup").exists()
