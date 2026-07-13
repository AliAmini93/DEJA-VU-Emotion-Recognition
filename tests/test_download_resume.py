"""Tests for download_one() in scripts/00_download_dejavu_zenodo.py against a
local stdlib HTTP server that can either honor or ignore Range requests.

No network access to Zenodo is used. RAW_DOWNLOADS_DIR / LOG_DIR are
monkeypatched to a pytest tmp_path so tests never touch real project
directories. MAX_RETRIES / backoff are monkeypatched down so failure-path
tests stay fast.
"""
from __future__ import annotations

import hashlib
import http.server
import importlib.util
import threading
from pathlib import Path

import pytest
import requests

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
_spec = importlib.util.spec_from_file_location(
    "download_dejavu_zenodo", SCRIPTS_DIR / "00_download_dejavu_zenodo.py"
)
downloader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(downloader)

CONTENT = (b"DEJA-VU-SAMPLE-PHYSIOLOGICAL-BYTES-" * 500)  # deterministic fixture payload
CONTENT_SHA256 = hashlib.sha256(CONTENT).hexdigest()


class RangeAwareHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # silence default stderr logging
        pass

    def do_GET(self):
        if self.path == "/range_ok":
            self._serve_honoring_range(CONTENT)
        elif self.path == "/range_ignored":
            self._serve_ignoring_range(CONTENT)
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_honoring_range(self, content: bytes):
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.split("=", 1)[1].split("-", 1)[0])
            body = content[start:]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(content) - 1}/{len(content)}")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    def _serve_ignoring_range(self, content: bytes):
        # Always returns the full body with 200, even if a Range header was sent.
        self.send_response(200)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


@pytest.fixture(scope="module")
def http_server():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RangeAwareHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(timeout=5)


@pytest.fixture
def base_url(http_server):
    port = http_server.server_address[1]
    return f"http://127.0.0.1:{port}"


@pytest.fixture(autouse=True)
def isolate_downloader(tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "RAW_DOWNLOADS_DIR", tmp_path / "raw_downloads")
    monkeypatch.setattr(downloader, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(downloader, "MAX_RETRIES", 2)
    monkeypatch.setattr(downloader, "BACKOFF_BASE_S", 0.01)
    monkeypatch.setattr(downloader, "BACKOFF_MAX_S", 0.02)
    downloader.stop_event.clear()
    yield
    downloader.stop_event.clear()


def make_row(url: str, size: int = len(CONTENT), checksum: str = f"sha256:{CONTENT_SHA256}",
             relpath: str = "sample.bin") -> dict:
    return {
        "filename": relpath,
        "relative_output_path": relpath,
        "size_bytes": str(size),
        "checksum_raw": checksum,
        "download_url": url,
    }


def test_range_honored_resumes_from_partial_file(base_url, tmp_path):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    row = make_row(f"{base_url}/range_ok")
    part_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin.part"
    split = len(CONTENT) // 2
    part_path.write_bytes(CONTENT[:split])  # simulates an interrupted prior download

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "RESUMED_AND_VERIFIED"
    assert result["checksum_status"] == "OK"
    final_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin"
    assert final_path.read_bytes() == CONTENT
    assert not part_path.exists()  # renamed away after verification


def test_range_ignored_restarts_file_safely(base_url):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    row = make_row(f"{base_url}/range_ignored")
    part_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin.part"
    part_path.write_bytes(b"GARBAGE-FROM-A-DIFFERENT-ATTEMPT" * 3)  # stale partial content

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "DOWNLOADED_AND_VERIFIED"  # not "resumed" - full restart
    assert result["checksum_status"] == "OK"
    final_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin"
    assert final_path.read_bytes() == CONTENT


def test_existing_verified_file_is_not_redownloaded(base_url):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    final_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin"
    final_path.write_bytes(CONTENT)  # already correct and complete
    row = make_row("http://127.0.0.1:1/unreachable-should-not-be-hit")

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "VERIFIED_EXISTING"
    assert result["checksum_status"] == "OK"


def test_wrong_declared_size_fails_after_retries(base_url):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    row = make_row(f"{base_url}/range_ok", size=len(CONTENT) + 999)  # server can never satisfy this

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "FAILED"
    assert "exhausted" in result["error"]
    # partial data is preserved on disk for forensic inspection, not deleted
    assert (downloader.RAW_DOWNLOADS_DIR / "sample.bin.part").exists()


def test_checksum_mismatch_is_detected_and_part_file_kept(base_url):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    wrong_checksum = "sha256:" + ("0" * 64)
    row = make_row(f"{base_url}/range_ok", checksum=wrong_checksum)

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "FAILED"
    assert result["checksum_status"] == "MISMATCH"
    part_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin.part"
    assert part_path.exists()  # not silently deleted
    assert part_path.read_bytes() == CONTENT
    final_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin"
    assert not final_path.exists()  # never renamed into place


def test_stop_event_interrupts_before_starting_new_attempt(base_url):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    row = make_row(f"{base_url}/range_ok")
    downloader.stop_event.set()

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "INTERRUPTED"
    final_path = downloader.RAW_DOWNLOADS_DIR / "sample.bin"
    assert not final_path.exists()


def test_path_traversal_in_manifest_row_is_rejected(base_url):
    downloader.RAW_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
    row = make_row(f"{base_url}/range_ok", relpath="../../etc/passwd")

    session = requests.Session()
    result = downloader.download_one(session, row)

    assert result["download_status"] == "FAILED"
    assert result["checksum_status"] == "INVALID"
