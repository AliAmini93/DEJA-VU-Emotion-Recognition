"""Tests for participant/session identity parsing and conflict detection in
scripts/dejavu_lib.py — the logic underpinning
docs/dejavu_identity_conflict_audit.md."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from dejavu_lib import (  # noqa: E402
    identity_conflict,
    parse_participant_session_from_filename,
    parse_participant_session_from_path,
)


def test_parse_from_path_normal_case():
    ident = parse_participant_session_from_path(
        "DEJA-VU/raw/sub-P017/ses-S002/eeg/whatever.xdf"
    )
    assert ident == {"subject": "P017", "session": "S002"}


def test_parse_from_filename_normal_case():
    ident = parse_participant_session_from_filename(
        "sub-P017_ses-S002_task-Default_run-001_eeg.xdf"
    )
    assert ident == {"subject": "P017", "session": "S002"}


def test_parse_from_filename_anomalous_p666_case():
    ident = parse_participant_session_from_filename(
        "sub-P666_ses-S001_task-Default_run-001_eeg.xdf"
    )
    assert ident == {"subject": "P666", "session": "S001"}


def test_parse_from_path_ignores_filename_content():
    # Regression guard: the path parser must not be fooled by a differently
    # named file sitting inside a correctly-named directory.
    ident = parse_participant_session_from_path(
        "DEJA-VU/raw/sub-P017/ses-S002/eeg/sub-P666_ses-S001_task-Default_run-001_eeg.xdf"
    )
    assert ident == {"subject": "P017", "session": "S002"}


def test_parse_missing_tokens_returns_none():
    ident = parse_participant_session_from_path("DEJA-VU/data.xlsx")
    assert ident == {"subject": None, "session": None}


def test_identity_conflict_detects_the_real_p666_case():
    path_id = parse_participant_session_from_path(
        "DEJA-VU/raw/sub-P017/ses-S002/eeg/sub-P666_ses-S001_task-Default_run-001_eeg.xdf"
    )
    filename_id = parse_participant_session_from_filename(
        "sub-P666_ses-S001_task-Default_run-001_eeg.xdf"
    )
    assert identity_conflict(path_id, filename_id) is True


def test_identity_conflict_false_for_normal_file():
    path_id = parse_participant_session_from_path(
        "DEJA-VU/raw/sub-P001/ses-S001/eeg/sub-P001_ses-S001_task-Default_run-001_eeg.xdf"
    )
    filename_id = parse_participant_session_from_filename(
        "sub-P001_ses-S001_task-Default_run-001_eeg.xdf"
    )
    assert identity_conflict(path_id, filename_id) is False


def test_identity_conflict_false_when_one_side_missing():
    # A filename with no parseable identity at all must not spuriously conflict.
    path_id = {"subject": "P017", "session": "S002"}
    filename_id = {"subject": None, "session": None}
    assert identity_conflict(path_id, filename_id) is False


def test_identity_conflict_detects_session_only_mismatch():
    path_id = {"subject": "P017", "session": "S002"}
    filename_id = {"subject": "P017", "session": "S001"}
    assert identity_conflict(path_id, filename_id) is True
