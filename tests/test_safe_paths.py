"""Tests for scripts/dejavu_lib.safe_join: nested-path acceptance and
path-traversal rejection."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import pytest  # noqa: E402
from dejavu_lib import PathTraversalError, safe_join  # noqa: E402


def test_simple_filename_is_accepted(tmp_path):
    result = safe_join(tmp_path, "DEJA-VU.rar")
    assert result == (tmp_path / "DEJA-VU.rar").resolve()


def test_safe_nested_path_is_accepted(tmp_path):
    result = safe_join(tmp_path, "subject01/session1/eeg.xdf")
    expected = (tmp_path / "subject01" / "session1" / "eeg.xdf").resolve()
    assert result == expected


@pytest.mark.parametrize(
    "bad_path",
    [
        "../outside.rar",
        "../../etc/passwd",
        "sub/../../escape.rar",
        "a/b/../../../c.rar",
    ],
)
def test_parent_traversal_is_rejected(tmp_path, bad_path):
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, bad_path)


def test_absolute_path_is_rejected(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "/etc/passwd")


def test_empty_path_is_rejected(tmp_path):
    with pytest.raises(PathTraversalError):
        safe_join(tmp_path, "")


def test_traversal_that_stays_inside_base_is_allowed(tmp_path):
    # sub/../file.rar normalizes to file.rar, which is still inside base_dir.
    result = safe_join(tmp_path, "sub/../file.rar")
    assert result == (tmp_path / "file.rar").resolve()
