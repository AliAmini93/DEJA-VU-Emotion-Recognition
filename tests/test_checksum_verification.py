"""Tests for scripts/dejavu_lib checksum parsing, computation, and file
verification."""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pytest  # noqa: E402
from dejavu_lib import compute_checksum, parse_checksum, verify_file  # noqa: E402


def test_parse_checksum_valid_md5():
    algo, value = parse_checksum("md5:0815b7d78915d132084f4ef497cef6d0")
    assert algo == "md5"
    assert value == "0815b7d78915d132084f4ef497cef6d0"


def test_parse_checksum_valid_sha256():
    algo, value = parse_checksum("sha256:" + "a" * 64)
    assert algo == "sha256"
    assert value == "a" * 64


def test_parse_checksum_missing_colon_is_malformed():
    with pytest.raises(ValueError):
        parse_checksum("0815b7d78915d132084f4ef497cef6d0")


def test_parse_checksum_empty_string_is_malformed():
    with pytest.raises(ValueError):
        parse_checksum("")


def test_parse_checksum_unsupported_algorithm():
    with pytest.raises(ValueError):
        parse_checksum("crc32:deadbeef")


def test_parse_checksum_non_hex_value_is_malformed():
    with pytest.raises(ValueError):
        parse_checksum("md5:not-a-hex-value!!")


def test_compute_checksum_matches_hashlib(tmp_path):
    content = b"DEJA-VU test content" * 1000
    f = tmp_path / "sample.bin"
    f.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert compute_checksum(f, "sha256") == expected


def test_compute_checksum_md5(tmp_path):
    content = b"another sample payload"
    f = tmp_path / "sample2.bin"
    f.write_bytes(content)
    expected = hashlib.md5(content).hexdigest()
    assert compute_checksum(f, "md5") == expected


def test_verify_file_ok(tmp_path):
    content = b"x" * 4096
    f = tmp_path / "good.bin"
    f.write_bytes(content)
    checksum_raw = f"sha256:{hashlib.sha256(content).hexdigest()}"
    result = verify_file(f, expected_size=len(content), checksum_raw=checksum_raw)
    assert result.ok
    assert result.size_match
    assert result.checksum_match


def test_verify_file_missing(tmp_path):
    f = tmp_path / "does_not_exist.bin"
    result = verify_file(f, expected_size=100, checksum_raw="sha256:" + "0" * 64)
    assert not result.ok
    assert not result.exists


def test_verify_file_wrong_size(tmp_path):
    content = b"y" * 100
    f = tmp_path / "wrong_size.bin"
    f.write_bytes(content)
    checksum_raw = f"sha256:{hashlib.sha256(content).hexdigest()}"
    result = verify_file(f, expected_size=999, checksum_raw=checksum_raw)
    assert not result.ok
    assert result.exists
    assert not result.size_match


def test_verify_file_checksum_mismatch(tmp_path):
    content = b"z" * 100
    f = tmp_path / "bad_checksum.bin"
    f.write_bytes(content)
    wrong_checksum = "sha256:" + ("0" * 64)
    result = verify_file(f, expected_size=len(content), checksum_raw=wrong_checksum)
    assert not result.ok
    assert result.size_match
    assert not result.checksum_match
