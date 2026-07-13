"""Tests for the Zenodo metadata validator in
scripts/00_fetch_dejavu_zenodo_metadata.py.

The script's filename starts with digits, so it isn't a valid `import`
target; it is loaded by file path via importlib instead.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "fetch_dejavu_zenodo_metadata", SCRIPTS_DIR / "00_fetch_dejavu_zenodo_metadata.py"
)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

validate_record = _module.validate_record
RECORD_ID = _module.RECORD_ID


def make_valid_record() -> dict:
    return {
        "id": RECORD_ID,
        "conceptrecid": "17773124",
        "doi": "10.5281/zenodo.17773125",
        "conceptdoi": "10.5281/zenodo.17773124",
        "created": "2025-12-01T03:08:02.809675+00:00",
        "updated": "2025-12-01T03:08:03.249352+00:00",
        "metadata": {
            "title": "DEJA-VU: A multimodal dataset for emotional transition analysis in virtual reality",
            "publication_date": "2025-12-01",
            "version": "1.0.0",
            "access_right": "open",
            "license": {"id": "cc-by-4.0"},
            "creators": [{"name": "Example, Author"}],
            "description": "some description",
        },
        "files": [
            {
                "key": "DEJA-VU.rar",
                "size": 3996522166,
                "checksum": "md5:0815b7d78915d132084f4ef497cef6d0",
                "links": {"self": "https://zenodo.org/api/records/17773125/files/DEJA-VU.rar/content"},
            },
        ],
    }


def test_valid_record_has_no_errors():
    assert validate_record(make_valid_record()) == []


def test_missing_checksum_field_is_flagged():
    record = make_valid_record()
    del record["files"][0]["checksum"]
    errors = validate_record(record)
    assert any("checksum" in e for e in errors) or any("missing required field: 'checksum'" in e for e in errors)


def test_malformed_checksum_no_colon_is_flagged():
    record = make_valid_record()
    record["files"][0]["checksum"] = "0815b7d78915d132084f4ef497cef6d0"  # no algorithm prefix
    errors = validate_record(record)
    assert any("algorithm:value" in e for e in errors)


def test_checksum_algorithm_parsing_accepts_sha256_form():
    record = make_valid_record()
    record["files"][0]["checksum"] = "sha256:" + "a" * 64
    assert validate_record(record) == []


def test_record_id_mismatch_is_flagged():
    record = make_valid_record()
    record["id"] = 99999999
    errors = validate_record(record)
    assert any("record id mismatch" in e for e in errors)


def test_missing_top_level_field_is_flagged():
    record = make_valid_record()
    del record["doi"]
    errors = validate_record(record)
    assert any("missing required top-level field: 'doi'" in e for e in errors)


def test_missing_metadata_field_is_flagged():
    record = make_valid_record()
    del record["metadata"]["version"]
    errors = validate_record(record)
    assert any("missing required metadata field: 'version'" in e for e in errors)


def test_empty_files_list_is_flagged():
    record = make_valid_record()
    record["files"] = []
    errors = validate_record(record)
    assert any("files field missing, not a list, or empty" in e for e in errors)


def test_negative_size_is_flagged():
    record = make_valid_record()
    record["files"][0]["size"] = -1
    errors = validate_record(record)
    assert any("invalid size" in e for e in errors)


def test_two_file_record_is_valid():
    record = make_valid_record()
    record["files"].append({
        "key": "DEJA_VU_code.rar",
        "size": 57777,
        "checksum": "md5:0747b65d5bbe215c621e435d546fe1c0",
        "links": {"self": "https://zenodo.org/api/records/17773125/files/DEJA_VU_code.rar/content"},
    })
    assert validate_record(record) == []


def test_does_not_mutate_input(tmp_path):
    record = make_valid_record()
    snapshot = copy.deepcopy(record)
    validate_record(record)
    assert record == snapshot
