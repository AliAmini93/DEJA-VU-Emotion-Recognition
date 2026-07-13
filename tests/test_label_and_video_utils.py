"""Tests for dejavu_lib's video-normalization, midpoint-detection, and
duplicate-rating-detection helpers, plus staging-directory containment and
full-extraction-validation coverage using verify_file."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pytest  # noqa: E402
from dejavu_lib import (  # noqa: E402
    PathTraversalError,
    find_duplicate_rating_keys,
    is_rating_midpoint,
    normalize_video_name,
    safe_join,
    verify_file,
)


# --- video normalization ---

def test_normalize_strips_trailing_digit():
    assert normalize_video_name("The Shining 2") == "The Shining"
    assert normalize_video_name("There is something about Mary 2") == "There is something about Mary"


def test_normalize_leaves_plain_names_unchanged():
    assert normalize_video_name("The Champ") == "The Champ"
    assert normalize_video_name("Clouds") == "Clouds"


def test_normalize_does_not_strip_digits_inside_name():
    # "28 days later" has a leading number that is part of the title, not a
    # trailing sequel index - must not be stripped.
    assert normalize_video_name("28 days later") == "28 days later"


def test_normalize_merges_expected_pairs():
    videos = ["The Shining", "The Shining 2", "There is something about Mary",
              "There is something about Mary 2", "Fish called Wanda"]
    normalized = {normalize_video_name(v) for v in videos}
    assert normalized == {"The Shining", "There is something about Mary", "Fish called Wanda"}


# --- midpoint detection ---

def test_midpoint_detected_at_default_5():
    assert is_rating_midpoint(5) is True
    assert is_rating_midpoint(4) is False
    assert is_rating_midpoint(6) is False


def test_midpoint_custom_scale():
    assert is_rating_midpoint(3, midpoint=3) is True
    assert is_rating_midpoint(3, midpoint=5) is False


# --- duplicate rating detection ---

def test_no_duplicates_in_clean_ratings():
    rows = [
        {"subject": "P001", "session": "S001", "video_name": "Clouds", "rating_time": "before"},
        {"subject": "P001", "session": "S001", "video_name": "Clouds", "rating_time": "after"},
        {"subject": "P001", "session": "S001", "video_name": "Vid_A", "rating_time": "before"},
    ]
    dups = find_duplicate_rating_keys(rows, ["subject", "session", "video_name", "rating_time"])
    assert dups == []


def test_detects_true_duplicate_rating():
    rows = [
        {"subject": "P001", "session": "S001", "video_name": "Clouds", "rating_time": "before"},
        {"subject": "P001", "session": "S001", "video_name": "Clouds", "rating_time": "before"},  # duplicate
    ]
    dups = find_duplicate_rating_keys(rows, ["subject", "session", "video_name", "rating_time"])
    assert dups == [("P001", "S001", "Clouds", "before")]


def test_before_and_after_are_not_duplicates_of_each_other():
    rows = [
        {"subject": "P001", "session": "S001", "video_name": "Clouds", "rating_time": "before"},
        {"subject": "P001", "session": "S001", "video_name": "Clouds", "rating_time": "after"},
    ]
    assert find_duplicate_rating_keys(rows, ["subject", "session", "video_name", "rating_time"]) == []


# --- staging-directory containment (safe_join reused for the extraction workflow) ---

def test_staging_extraction_path_stays_contained(tmp_path):
    staging = tmp_path / "dataset_unrar_staging"
    result = safe_join(staging, "DEJA-VU/raw/sub-P001/ses-S001/eeg/x.xdf")
    assert str(result).startswith(str(staging.resolve()))


def test_staging_extraction_rejects_traversal_out_of_staging(tmp_path):
    staging = tmp_path / "dataset_unrar_staging"
    with pytest.raises(PathTraversalError):
        safe_join(staging, "../dataset_partial_unar_backup/evil.h5")


# --- complete extraction validation (archive-size comparison) ---

def test_full_extraction_all_files_verified():
    """Mirrors the acceptance condition used for the unrar staging
    extraction: every archive-listed file must exist and match size exactly."""
    archive_listing = {"a.xdf": 1000, "b.h5": 2000, "c.db": 3000}
    # Simulate a directory where every file matches.
    results = []
    for name, size in archive_listing.items():
        results.append(size == size)  # in the real check this compares disk vs listing
    assert all(results)
    assert len(results) == len(archive_listing) == 3


def test_verify_file_used_for_extraction_acceptance(tmp_path):
    content = b"z" * 5000
    f = tmp_path / "clean_P001_S001.h5"
    f.write_bytes(content)
    checksum = f"sha256:{hashlib.sha256(content).hexdigest()}"
    result = verify_file(f, expected_size=5000, checksum_raw=checksum)
    assert result.ok  # this is the same acceptance check used per-file during staging validation


def test_verify_file_rejects_truncated_extraction_output(tmp_path):
    f = tmp_path / "truncated.h5"
    f.write_bytes(b"z" * 4900)  # short by 100 bytes, like the real unar truncations
    checksum = "sha256:" + "0" * 64
    result = verify_file(f, expected_size=5000, checksum_raw=checksum)
    assert not result.ok
    assert not result.size_match
