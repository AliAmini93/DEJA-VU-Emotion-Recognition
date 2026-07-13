#!/usr/bin/env python
"""Fetch and validate the official Zenodo record metadata for DEJA-VU.

Fetches https://zenodo.org/api/records/17773125 (record ID is fixed and
verified against the response), writes the raw, unmodified JSON response to
/mnt/HDD/AliWorks/DEJA-VU/metadata/zenodo_record_17773125.json, writes its
SHA-256 to /mnt/HDD/AliWorks/DEJA-VU/checksums/zenodo_record_17773125.json.sha256,
and validates that the fields required for acquisition are present.

This script does not download any dataset file. It only fetches the small
JSON metadata record.

Exit codes:
  0  metadata fetched and validated successfully
  1  network/HTTP failure after exhausting retries
  2  metadata fetched but malformed or internally inconsistent
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

RECORD_ID = 17773125
API_URL = f"https://zenodo.org/api/records/{RECORD_ID}"
USER_AGENT = (
    "DEJA-VU-Emotion-Recognition-audit/1.0 "
    "(+https://github.com/AliAmini93/DEJA-VU-Emotion-Recognition; "
    "contact: research data acquisition script)"
)

CONNECT_TIMEOUT_S = 10
READ_TIMEOUT_S = 30
MAX_RETRIES = 5
BACKOFF_BASE_S = 2.0
BACKOFF_MAX_S = 60.0
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

DATA_ROOT = Path("/mnt/HDD/AliWorks/DEJA-VU")
METADATA_DIR = DATA_ROOT / "metadata"
CHECKSUMS_DIR = DATA_ROOT / "checksums"
OUTPUT_JSON = METADATA_DIR / f"zenodo_record_{RECORD_ID}.json"
OUTPUT_SHA256 = CHECKSUMS_DIR / f"zenodo_record_{RECORD_ID}.json.sha256"

REQUIRED_TOP_LEVEL_FIELDS = ["id", "conceptrecid", "doi", "conceptdoi", "created", "updated", "files"]
REQUIRED_METADATA_FIELDS = ["title", "publication_date", "version", "access_right", "license", "creators", "description"]
REQUIRED_FILE_FIELDS = ["key", "size", "checksum", "links"]


def log(msg: str) -> None:
    print(f"[fetch-zenodo-metadata] {msg}", file=sys.stderr, flush=True)


def fetch_with_retries(url: str) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            log(f"attempt {attempt}/{MAX_RETRIES}: GET {url}")
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
                timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            log(f"network error: {exc!r}")
        else:
            if resp.status_code == 200:
                return resp
            if resp.status_code in RETRYABLE_STATUS:
                log(f"retryable HTTP status {resp.status_code}: {resp.text[:300]!r}")
                last_exc = requests.HTTPError(f"HTTP {resp.status_code}")
            else:
                # Non-retryable HTTP error (e.g. 404, 401, 403) - fail fast.
                resp.raise_for_status()

        if attempt < MAX_RETRIES:
            sleep_s = min(BACKOFF_BASE_S * (2 ** (attempt - 1)), BACKOFF_MAX_S)
            log(f"backing off {sleep_s:.1f}s before retry")
            time.sleep(sleep_s)

    raise RuntimeError(f"exhausted {MAX_RETRIES} retries fetching {url}") from last_exc


def validate_record(data: dict) -> list[str]:
    """Return a list of validation error strings (empty list = valid)."""
    errors: list[str] = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            errors.append(f"missing required top-level field: {field!r}")

    if data.get("id") != RECORD_ID:
        errors.append(f"record id mismatch: expected {RECORD_ID}, got {data.get('id')!r}")

    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("metadata field missing or not an object")
        metadata = {}
    else:
        for field in REQUIRED_METADATA_FIELDS:
            if field not in metadata:
                errors.append(f"missing required metadata field: {field!r}")

    files = data.get("files")
    if not isinstance(files, list) or len(files) == 0:
        errors.append("files field missing, not a list, or empty")
    else:
        for i, f in enumerate(files):
            if not isinstance(f, dict):
                errors.append(f"files[{i}] is not an object")
                continue
            for field in REQUIRED_FILE_FIELDS:
                if field not in f:
                    errors.append(f"files[{i}] missing required field: {field!r}")
            checksum = f.get("checksum", "")
            if ":" not in str(checksum):
                errors.append(f"files[{i}] checksum has no 'algorithm:value' form: {checksum!r}")
            size = f.get("size")
            if not isinstance(size, int) or size <= 0:
                errors.append(f"files[{i}] has invalid size: {size!r}")
            link = f.get("links", {}).get("self")
            if not link or urlparse(link).scheme not in ("http", "https"):
                errors.append(f"files[{i}] has invalid or missing download link: {link!r}")

    return errors


def main() -> int:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    CHECKSUMS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        resp = fetch_with_retries(API_URL)
    except Exception as exc:
        log(f"FAILED to fetch metadata: {exc!r}")
        return 1

    raw_bytes = resp.content  # write exactly what the server sent, unmodified

    try:
        data = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        log(f"FAILED: response is not valid JSON: {exc!r}")
        return 2

    errors = validate_record(data)
    if errors:
        log("FAILED: metadata is malformed or internally inconsistent:")
        for e in errors:
            log(f"  - {e}")
        return 2

    OUTPUT_JSON.write_bytes(raw_bytes)
    digest = hashlib.sha256(raw_bytes).hexdigest()
    OUTPUT_SHA256.write_text(f"{digest}  {OUTPUT_JSON.name}\n")

    log(f"OK: record {data['id']} validated, {len(data['files'])} file(s), "
        f"{sum(f['size'] for f in data['files'])} total bytes")
    log(f"wrote {OUTPUT_JSON} ({len(raw_bytes)} bytes)")
    log(f"wrote {OUTPUT_SHA256} (sha256={digest})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
