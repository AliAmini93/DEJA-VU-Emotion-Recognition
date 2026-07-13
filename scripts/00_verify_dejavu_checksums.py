#!/usr/bin/env python
"""Independently re-verify every official DEJA-VU file already present in
raw_downloads/ against the manifest's official size and checksum.

This is deliberately separate from the downloader so verification can be
re-run at any time (e.g. after a machine restart, or before trusting files
for later use) without re-downloading anything.

Writes docs/dejavu_checksum_report.csv.

Exit codes:
  0  every manifest file present, correctly sized, and checksum-verified
  1  at least one manifest file missing, truncated, or checksum-invalid
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dejavu_lib import (  # noqa: E402
    PathTraversalError,
    human_size,
    read_manifest,
    safe_join,
    verify_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "dejavu_download_manifest.csv"
RAW_DOWNLOADS_DIR = Path("/mnt/HDD/AliWorks/DEJA-VU/raw_downloads")
REPORT_PATH = REPO_ROOT / "docs" / "dejavu_checksum_report.csv"

REPORT_FIELDNAMES = [
    "filename", "expected_size_bytes", "actual_size_bytes", "size_match",
    "checksum_algorithm", "expected_checksum", "actual_checksum",
    "checksum_match", "status", "verified_at",
]


def main() -> int:
    rows = read_manifest(DEFAULT_MANIFEST)
    if not rows:
        print(f"manifest is empty or missing: {DEFAULT_MANIFEST}", file=sys.stderr)
        return 1

    report_rows = []
    all_ok = True
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S")

    for row in rows:
        filename = row["filename"]
        expected_size = int(row["size_bytes"])
        try:
            path = safe_join(RAW_DOWNLOADS_DIR, row["relative_output_path"])
        except PathTraversalError as exc:
            print(f"{filename}: REJECTED unsafe path: {exc}", file=sys.stderr)
            all_ok = False
            report_rows.append({
                "filename": filename, "expected_size_bytes": expected_size,
                "actual_size_bytes": "", "size_match": False,
                "checksum_algorithm": "", "expected_checksum": "",
                "actual_checksum": "", "checksum_match": False,
                "status": "UNSAFE_PATH", "verified_at": now,
            })
            continue

        result = verify_file(path, expected_size, row["checksum_raw"])
        status = "VERIFIED" if result.ok else ("MISSING" if not result.exists else "MISMATCH")
        if not result.ok:
            all_ok = False

        print(f"{filename}: {status} "
              f"(size {result.actual_size_bytes}/{result.expected_size_bytes}, "
              f"checksum {'match' if result.checksum_match else 'MISMATCH' if result.exists else 'n/a'})")

        report_rows.append({
            "filename": filename,
            "expected_size_bytes": result.expected_size_bytes,
            "actual_size_bytes": result.actual_size_bytes if result.actual_size_bytes is not None else "",
            "size_match": result.size_match,
            "checksum_algorithm": result.checksum_algorithm,
            "expected_checksum": result.expected_checksum,
            "actual_checksum": result.actual_checksum or "",
            "checksum_match": result.checksum_match,
            "status": status,
            "verified_at": now,
        })

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"\nchecksum report written to {REPORT_PATH}")
    print(f"total_bytes_verified: {human_size(sum(int(r['actual_size_bytes'] or 0) for r in report_rows if r['status'] == 'VERIFIED'))}")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
