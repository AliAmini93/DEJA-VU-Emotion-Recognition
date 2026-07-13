"""Tests for scripts/00_validate_archive_members.py::validate_members
against synthetic ArchiveMember lists (no real archive needed)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from archive_listing import ArchiveMember  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "validate_archive_members", SCRIPTS_DIR / "00_validate_archive_members.py"
)
validator_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validator_module)
validate_members = validator_module.validate_members


def m(path, size=100, is_dir=False, is_link=False):
    return ArchiveMember(raw_path=path, size_bytes=size, is_directory=is_dir, is_symlink=is_link)


def test_safe_nested_paths_produce_no_issues(tmp_path):
    members = [m("DEJA-VU/data.xlsx"), m("DEJA-VU/raw/sub-P001/ses-S001/eeg/x.xdf")]
    assert validate_members(members, tmp_path) == []


def test_path_traversal_dotdot_is_rejected(tmp_path):
    members = [m("DEJA-VU/../../etc/passwd")]
    issues = validate_members(members, tmp_path)
    assert len(issues) == 1
    assert "'..' path component" in issues[0]["issue"]


def test_absolute_path_is_rejected(tmp_path):
    members = [m("/etc/passwd")]
    issues = validate_members(members, tmp_path)
    assert any("absolute path" in i["issue"] for i in issues)


def test_embedded_null_byte_is_rejected(tmp_path):
    members = [m("DEJA-VU/evil\x00.xdf")]
    issues = validate_members(members, tmp_path)
    assert any("null character" in i["issue"] for i in issues)


def test_duplicate_normalized_paths_are_rejected(tmp_path):
    members = [m("DEJA-VU/data.xlsx"), m("DEJA-VU/./data.xlsx")]
    issues = validate_members(members, tmp_path)
    assert any("duplicate normalized path" in i["issue"] for i in issues)


def test_case_collision_paths_are_rejected(tmp_path):
    members = [m("DEJA-VU/Data.xlsx"), m("DEJA-VU/data.xlsx")]
    issues = validate_members(members, tmp_path)
    assert any("case-collision" in i["issue"] for i in issues)


def test_distinct_paths_differing_only_in_subdir_case_are_not_flagged_as_duplicates(tmp_path):
    # Same casefold but genuinely different content is still a case-collision risk
    members = [m("DEJA-VU/raw/x.xdf"), m("DEJA-VU/RAW/x.xdf")]
    issues = validate_members(members, tmp_path)
    assert any("case-collision" in i["issue"] for i in issues)


def test_symlink_member_is_rejected(tmp_path):
    members = [m("DEJA-VU/sneaky_link", is_link=True)]
    issues = validate_members(members, tmp_path)
    assert any("symlink" in i["issue"] for i in issues)


def test_directories_are_not_flagged(tmp_path):
    members = [m("DEJA-VU", is_dir=True, size=0), m("DEJA-VU/raw", is_dir=True, size=0)]
    assert validate_members(members, tmp_path) == []


def test_multiple_distinct_safe_paths_all_pass(tmp_path):
    members = [m(f"DEJA-VU/segments/sub-P{i:03d}/S001_neutral_baseline.h5") for i in range(1, 29)]
    assert validate_members(members, tmp_path) == []
