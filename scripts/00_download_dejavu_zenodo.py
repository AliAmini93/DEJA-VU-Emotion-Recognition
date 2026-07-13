#!/usr/bin/env python
"""Resumable, checksum-verified downloader for the official DEJA-VU Zenodo files.

Reads the manifest produced from official Zenodo metadata
(docs/dejavu_download_manifest.csv by default), downloads each file into
/mnt/HDD/AliWorks/DEJA-VU/raw_downloads/ using HTTP Range resume, verifies
exact size and checksum, and only then atomically renames the `.part` file to
its final name. The manifest is updated atomically after every file.

Never overwrites an already-verified file. Never deletes a `.part` file on
Ctrl+C. At most 3 concurrent downloads. Bounded retries with exponential
backoff. Rejects any output path that would escape raw_downloads/.

Exit codes:
  0  every official file present and checksum-verified
  1  at least one official file missing, truncated, or checksum-invalid
  2  pre-flight check failed (insufficient disk space, bad manifest, etc.)
"""
from __future__ import annotations

import argparse
import concurrent.futures
import signal
import sys
import threading
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dejavu_lib import (  # noqa: E402
    MANIFEST_FIELDNAMES,
    PathTraversalError,
    compute_checksum,
    human_size,
    parse_checksum,
    read_manifest,
    safe_join,
    write_manifest_atomic,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "docs" / "dejavu_download_manifest.csv"
RAW_DOWNLOADS_DIR = Path("/mnt/HDD/AliWorks/DEJA-VU/raw_downloads")
LOG_DIR = Path("/mnt/HDD/AliWorks/DEJA-VU/logs")

USER_AGENT = (
    "DEJA-VU-Emotion-Recognition-audit/1.0 "
    "(+https://github.com/AliAmini93/DEJA-VU-Emotion-Recognition; "
    "contact: research data acquisition script)"
)
CONNECT_TIMEOUT_S = 15
READ_TIMEOUT_S = 60
MAX_RETRIES = 5
BACKOFF_BASE_S = 3.0
BACKOFF_MAX_S = 120.0
MAX_CONCURRENCY = 3
DISK_HEADROOM_BYTES = 20 * (1024 ** 3)  # 20 GiB
STREAM_CHUNK = 1024 * 1024  # 1 MiB

stop_event = threading.Event()
log_lock = threading.Lock()
manifest_lock = threading.Lock()


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    with log_lock:
        print(line, flush=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / "download_dejavu_zenodo.log", "a") as fh:
            fh.write(line + "\n")


def free_space_bytes(path: Path) -> int:
    import shutil
    return shutil.disk_usage(path).free


def preflight(rows: list[dict]) -> None:
    RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    total = sum(int(r["size_bytes"]) for r in rows)
    free = free_space_bytes(RAW_DOWNLOADS_DIR)
    log(f"preflight: total_official_bytes={total} ({human_size(total)}), "
        f"free_space_bytes={free} ({human_size(free)}), "
        f"required_headroom={human_size(DISK_HEADROOM_BYTES)}")
    if free < total + DISK_HEADROOM_BYTES:
        raise SystemExit(
            f"Insufficient disk space: free={human_size(free)} < "
            f"required={human_size(total + DISK_HEADROOM_BYTES)} "
            f"(total {human_size(total)} + 20 GiB headroom)"
        )
    for r in rows:
        # Validate filenames are safe before any network activity.
        safe_join(RAW_DOWNLOADS_DIR, r["relative_output_path"])
        parse_checksum(r["checksum_raw"])


def download_one(session: requests.Session, row: dict) -> dict:
    """Download+verify a single manifest row. Returns the updated row dict."""
    result = dict(row)
    filename = row["filename"]
    url = row["download_url"]
    expected_size = int(row["size_bytes"])
    algorithm, expected_value = parse_checksum(row["checksum_raw"])

    try:
        final_path = safe_join(RAW_DOWNLOADS_DIR, row["relative_output_path"])
    except PathTraversalError as exc:
        log(f"{filename}: REJECTED unsafe output path: {exc}")
        result.update(download_status="FAILED", checksum_status="INVALID", error=str(exc))
        return result

    final_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = final_path.with_suffix(final_path.suffix + ".part")

    # Never overwrite a verified file: reverify existing final file first.
    if final_path.exists():
        log(f"{filename}: final file already exists, reverifying before skipping")
        actual_size = final_path.stat().st_size
        if actual_size == expected_size:
            actual_checksum = compute_checksum(final_path, algorithm)
            if actual_checksum == expected_value:
                log(f"{filename}: already verified, skipping (not re-downloaded)")
                result.update(
                    download_status="VERIFIED_EXISTING",
                    local_size_bytes=str(actual_size),
                    checksum_status="OK",
                    error="",
                )
                return result
        log(f"{filename}: existing final file FAILED reverification "
            f"(size or checksum mismatch) — refusing to overwrite automatically")
        result.update(
            download_status="EXISTING_INVALID",
            local_size_bytes=str(final_path.stat().st_size),
            checksum_status="MISMATCH",
            error="existing final file failed reverification; manual review required, not auto-deleted",
        )
        return result

    resumed = False
    attempt = 0
    while attempt < MAX_RETRIES:
        if stop_event.is_set():
            log(f"{filename}: stop requested, leaving .part intact")
            result.update(download_status="INTERRUPTED", error="interrupted by user")
            return result

        attempt += 1
        resume_pos = part_path.stat().st_size if part_path.exists() else 0
        headers = {"User-Agent": USER_AGENT}
        if resume_pos > 0:
            headers["Range"] = f"bytes={resume_pos}-"

        log(f"{filename}: attempt {attempt}/{MAX_RETRIES}, resume_pos={resume_pos}")
        try:
            with session.get(
                url, headers=headers, stream=True,
                timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
            ) as resp:
                if resp.status_code == 200 and resume_pos > 0:
                    # Range was ignored by the server: restart this file from scratch.
                    log(f"{filename}: server ignored Range header (got 200), restarting from 0")
                    resume_pos = 0
                    mode = "wb"
                elif resp.status_code == 206:
                    mode = "ab"
                    resumed = True  # a real partial-content response was honored
                elif resp.status_code == 200:
                    mode = "wb"
                else:
                    resp.raise_for_status()
                    mode = "wb"  # unreachable, raise_for_status will throw for >=400

                with open(part_path, mode) as fh:
                    for chunk in resp.iter_content(chunk_size=STREAM_CHUNK):
                        if stop_event.is_set():
                            log(f"{filename}: Ctrl+C during stream, leaving .part intact at "
                                f"{part_path.stat().st_size if part_path.exists() else 0} bytes")
                            result.update(download_status="INTERRUPTED", error="interrupted by user")
                            return result
                        if chunk:
                            fh.write(chunk)
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as exc:
            log(f"{filename}: attempt {attempt} network error: {exc!r}")
            if attempt < MAX_RETRIES:
                sleep_s = min(BACKOFF_BASE_S * (2 ** (attempt - 1)), BACKOFF_MAX_S)
                log(f"{filename}: backing off {sleep_s:.1f}s")
                time.sleep(sleep_s)
            continue

        actual_size = part_path.stat().st_size if part_path.exists() else 0
        if actual_size != expected_size:
            log(f"{filename}: size mismatch after streaming: got {actual_size}, "
                f"expected {expected_size} — will retry (part file kept)")
            if attempt < MAX_RETRIES:
                sleep_s = min(BACKOFF_BASE_S * (2 ** (attempt - 1)), BACKOFF_MAX_S)
                time.sleep(sleep_s)
            continue

        actual_checksum = compute_checksum(part_path, algorithm)
        if actual_checksum != expected_value:
            log(f"{filename}: CHECKSUM MISMATCH expected={expected_value} actual={actual_checksum} "
                f"— part file kept for inspection, not deleted")
            result.update(
                download_status="FAILED",
                local_size_bytes=str(actual_size),
                checksum_status="MISMATCH",
                error=f"checksum mismatch: expected {expected_value}, got {actual_checksum}",
            )
            return result

        # Verified: atomic rename only now.
        part_path.replace(final_path)
        log(f"{filename}: OK, verified and renamed to {final_path.name} ({human_size(actual_size)})")
        result.update(
            download_status="RESUMED_AND_VERIFIED" if resumed else "DOWNLOADED_AND_VERIFIED",
            local_size_bytes=str(actual_size),
            checksum_status="OK",
            error="",
        )
        return result

    log(f"{filename}: exhausted {MAX_RETRIES} attempts")
    result.update(
        download_status="FAILED",
        local_size_bytes=str(part_path.stat().st_size) if part_path.exists() else "0",
        checksum_status="PENDING",
        error=f"exhausted {MAX_RETRIES} retries",
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    def handle_sigint(signum, frame):
        log("SIGINT received — will stop after in-flight chunks, .part files preserved")
        stop_event.set()

    signal.signal(signal.SIGINT, handle_sigint)

    rows = read_manifest(args.manifest)
    if not rows:
        log("manifest is empty or missing rows")
        return 2

    try:
        preflight(rows)
    except SystemExit as exc:
        log(f"PREFLIGHT FAILED: {exc}")
        return 2
    except (PathTraversalError, ValueError) as exc:
        log(f"PREFLIGHT FAILED: manifest validation error: {exc}")
        return 2

    total_bytes = sum(int(r["size_bytes"]) for r in rows)
    session = requests.Session()

    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as pool:
        futures = {pool.submit(download_one, session, row): row for row in rows}
        try:
            for fut in concurrent.futures.as_completed(futures):
                results.append(fut.result())
        except KeyboardInterrupt:
            stop_event.set()
            for fut in futures:
                fut.cancel()
            raise

    # Update manifest atomically, preserving original row order.
    by_filename = {r["filename"]: r for r in results}
    updated_rows = [by_filename.get(r["filename"], r) for r in rows]
    with manifest_lock:
        write_manifest_atomic(args.manifest, updated_rows, MANIFEST_FIELDNAMES)
    log(f"manifest updated atomically: {args.manifest}")

    successful = [r for r in results if r["download_status"] in ("DOWNLOADED_AND_VERIFIED", "RESUMED_AND_VERIFIED", "VERIFIED_EXISTING")]
    resumed = [r for r in results if r["download_status"] == "RESUMED_AND_VERIFIED"]
    failed = [r for r in results if r["download_status"] not in ("DOWNLOADED_AND_VERIFIED", "RESUMED_AND_VERIFIED", "VERIFIED_EXISTING")]
    checksum_failures = [r for r in results if r["checksum_status"] == "MISMATCH"]
    verified_bytes = sum(int(r["local_size_bytes"] or 0) for r in successful)
    downloaded_bytes = sum(int(r["local_size_bytes"] or 0) for r in results)

    print("")
    print(f"total_expected_bytes: {total_bytes} ({human_size(total_bytes)})")
    print(f"downloaded_bytes: {downloaded_bytes} ({human_size(downloaded_bytes)})")
    print(f"verified_bytes: {verified_bytes} ({human_size(verified_bytes)})")
    print(f"remaining_bytes: {max(total_bytes - verified_bytes, 0)} ({human_size(max(total_bytes - verified_bytes, 0))})")
    print(f"total_files: {len(rows)}")
    print(f"successful_files: {len(successful)}")
    print(f"failed_files: {len(failed)}")
    print(f"resumed_files: {len(resumed)}")
    print(f"checksum_failures: {len(checksum_failures)}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
