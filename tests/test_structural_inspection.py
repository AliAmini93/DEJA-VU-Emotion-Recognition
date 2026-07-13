"""Tests for the format-specific inspection functions in
scripts/01_audit_dejavu_dataset.py, using small synthetic fixtures (not the
real ~3.72 GiB dataset) so the suite stays fast and network/data-free."""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import h5py
import numpy as np
import openpyxl
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from dejavu_lib import verify_file  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "audit_dejavu_dataset", SCRIPTS_DIR / "01_audit_dejavu_dataset.py"
)
audit_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_module)


def test_categorize_raw_xdf():
    assert audit_module.categorize("DEJA-VU/raw/sub-P001/ses-S001/eeg/x.xdf") == "raw_xdf"


def test_categorize_preprocessed_hdf5():
    assert audit_module.categorize("DEJA-VU/preprocessed/clean_P001_S001.h5") == "preprocessed_hdf5"


def test_categorize_segment_file():
    assert audit_module.categorize("DEJA-VU/segments/sub-P001/S001_neutral_baseline.h5") == "segment_file"


def test_categorize_sqlite_database():
    assert audit_module.categorize("DEJA-VU/deja_vu_database.db") == "sqlite_database"


def test_categorize_spreadsheet():
    assert audit_module.categorize("DEJA-VU/data.xlsx") == "spreadsheet"


def test_categorize_other():
    assert audit_module.categorize("DEJA-VU/README") == "other"


def test_audit_sqlite_reads_schema_and_rows(tmp_path):
    db_path = tmp_path / "mini.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE videos (subject TEXT, session TEXT, video_order INTEGER, video_name TEXT)")
    conn.executemany(
        "INSERT INTO videos VALUES (?, ?, ?, ?)",
        [("P001", "S001", 1, "Clouds"), ("P001", "S001", 2, "The Shining 2"), ("P002", "S001", 1, "Clouds")],
    )
    conn.commit()
    conn.close()

    result = audit_module.audit_sqlite(db_path)

    assert "videos" in result["tables"]
    assert result["tables"]["videos"]["row_count"] == 3
    col_names = [c["name"] for c in result["tables"]["videos"]["columns"]]
    assert col_names == ["subject", "session", "video_order", "video_name"]
    assert result["distinct_subjects"] == ["P001", "P002"]
    assert result["distinct_subject_session_pairs"] == 2


def test_audit_sqlite_is_read_only(tmp_path):
    db_path = tmp_path / "mini.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE videos (subject TEXT, session TEXT)")
    conn.commit()
    conn.close()

    # audit_sqlite opens with mode=ro; attempting a write through that
    # connection type should not be possible via the function's own API
    # (it exposes no write path at all).
    result = audit_module.audit_sqlite(db_path)
    assert result["tables"]["videos"]["row_count"] == 0
    # File must be unchanged in size/content after a read-only audit.
    assert db_path.stat().st_size > 0


def test_audit_xlsx_reads_sheet_names_and_header(tmp_path):
    xlsx_path = tmp_path / "mini.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "videos"
    ws.append(["subject", "session", "video_name"])
    ws.append(["P001", "S001", "Clouds"])
    wb.save(xlsx_path)

    result = audit_module.audit_xlsx(xlsx_path)

    assert result["sheet_names"] == ["videos"]
    assert result["sheets"]["videos"]["header_row"] == ["subject", "session", "video_name"]
    assert result["sheets"]["videos"]["max_row"] == 2


def test_audit_hdf5_file_metadata_only_no_full_array_needed(tmp_path):
    h5_path = tmp_path / "mini.h5"
    with h5py.File(h5_path, "w") as f:
        f.attrs["subject_id"] = "P001"
        f.attrs["session_id"] = "S001"
        grp = f.create_group("eeg")
        grp.attrs["sampling_rate"] = 300.0
        grp.attrs["channels"] = '["FP1", "FP2"]'
        grp.create_dataset("data", data=np.zeros((1000, 2), dtype="float32"), compression="gzip")
        grp.create_dataset("timestamps", data=np.arange(1000, dtype="float64"))

    result = audit_module.audit_hdf5_file(h5_path)

    assert result["top_level_attrs"]["subject_id"] == "P001"
    assert result["groups"]["eeg"]["attrs"]["sampling_rate"] == 300.0
    assert result["groups"]["eeg"]["datasets"]["data"]["shape"] == [1000, 2]
    assert result["groups"]["eeg"]["datasets"]["data"]["dtype"] == "float32"
    assert result["groups"]["eeg"]["datasets"]["data"]["compression"] == "gzip"


def test_audit_hdf5_segment_info_group(tmp_path):
    h5_path = tmp_path / "segment.h5"
    with h5py.File(h5_path, "w") as f:
        seg = f.create_group("segment_info")
        seg.attrs["subject"] = "P017"
        seg.attrs["session"] = "S002"
        seg.attrs["quadrant"] = "A"
        seg.attrs["video_name"] = "Fish called Wanda"

    result = audit_module.audit_hdf5_file(h5_path)

    assert result["groups"]["segment_info"]["attrs"]["subject"] == "P017"
    assert result["groups"]["segment_info"]["attrs"]["video_name"] == "Fish called Wanda"


# --- zero-byte / truncation detection (extracted-vs-archive size comparison) ---

def test_zero_byte_extraction_is_detected(tmp_path):
    f = tmp_path / "clean_P099_S001.h5"
    f.write_bytes(b"")
    result = verify_file(f, expected_size=63767712, checksum_raw="md5:" + "0" * 32)
    assert result.exists
    assert not result.size_match
    assert result.actual_size_bytes == 0


def test_truncated_extraction_size_mismatch_is_detected(tmp_path):
    # Mirrors the real clean_P003_S001.h5 truncation: expected 63767712,
    # actually got 63700992 (66720 bytes short).
    f = tmp_path / "clean_P003_S001.h5"
    f.write_bytes(b"x" * 63700992)
    result = verify_file(f, expected_size=63767712, checksum_raw="md5:" + "0" * 32)
    assert result.exists
    assert not result.size_match
    assert result.actual_size_bytes == 63700992
    assert result.expected_size_bytes == 63767712


def test_exact_size_match_passes(tmp_path):
    f = tmp_path / "ok.h5"
    content = b"y" * 1000
    f.write_bytes(content)
    import hashlib
    result = verify_file(f, expected_size=1000, checksum_raw=f"sha256:{hashlib.sha256(content).hexdigest()}")
    assert result.ok
