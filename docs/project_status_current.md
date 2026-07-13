# Project Status — Current

Last updated: 2026-07-13 (Europe/Vilnius)

## Phase

**Data-Only Audit.** No modeling, preprocessing, or training has occurred.

## Stage status

| Stage | Status |
|---|---|
| Stage 0 — Environment | COMPLETE: shared venv verified, pre/post snapshots taken, missing audit dependencies installed with zero protected-core-package changes, `pip check` passed, PyTorch+CUDA re-validated. |
| Stage 1 — Source verification | COMPLETE: official Zenodo record `17773125` fetched, checksummed, and field-validated. 2 official files identified, 3.72 GiB total. |
| Stage 2 — Acquisition | See `docs/dejavu_acquisition_report.md` for the outcome of this run. |

## What exists in this repository right now

- Environment audit carried over from the prior local-machine audit
  (`docs/environment_audit.md/json`, `docs/python_environment_inventory.csv`).
- Shared-environment policy and validation (`docs/shared_environment_policy.md`,
  `docs/shared_environment_validation.md/json`, `docs/environment_import_validation.md/json`).
- Official source verification (`docs/dejavu_source_verification.md/json`,
  `docs/dejavu_download_manifest.csv`).
- Resumable downloader + independent checksum verifier
  (`scripts/00_download_dejavu_zenodo.py`, `scripts/00_verify_dejavu_checksums.py`)
  plus their shared library (`scripts/dejavu_lib.py`) and metadata fetcher
  (`scripts/00_fetch_dejavu_zenodo_metadata.py`).
- 39-test suite (`tests/`) covering safe paths, checksum verification,
  Zenodo metadata validation, and download resume/restart/interrupt behavior
  — all passing against a local test server, no network required.
- Acquisition and checksum reports (`docs/dejavu_acquisition_report.md/json`,
  `docs/dejavu_checksum_report.csv`).
- Leakage risk register (`docs/leakage_risk_register.md`) — 10 risks logged,
  all OPEN pending raw-data inspection.
- Decision log (`docs/decision_log.md`) recording non-obvious decisions and
  one honestly-documented bug (nested `raw_downloads/` path, caught and fixed
  mid-download without data loss).

## What does NOT exist yet

- **The archives are not extracted.** `/mnt/HDD/AliWorks/DEJA-VU/extracted/`
  is empty. Extraction was attempted and failed for all 323 files across both
  archives: the only installed archiver (`7zip 23.01+dfsg-11`) is the Debian
  Free Software Guidelines build, which can list RAR/RAR5 contents but cannot
  decompress them (the RAR decompression codec is removed from that build).
  See `docs/dejavu_acquisition_report.md` for full detail. Fixing this
  requires installing `unar` or `unrar`, which is out of scope for this
  phase.
- Because extraction failed, `code/environment.yml` and
  `code/requirements.txt` inside `DEJA_VU_code.rar` could not be inspected —
  no dependency was added to this project based on official-code inspection.
- No inspection of the dataset's internal file/label/segment structure has
  occurred beyond the `7z l` archive **listing** (filenames, sizes, directory
  layout only — no file contents). All 10 leakage risks remain OPEN.
- No `configs/` or `folds/` content has been created — these depend on
  inspecting actual (not just listed) file contents against the leakage risk
  register first.

## Next permitted action

Get explicit approval to install a RAR5-capable extractor (`unar`
recommended — free/DFSG-compatible, or `unrar` — non-free but from the
format's original vendor), then extract both archives into
`/mnt/HDD/AliWorks/DEJA-VU/extracted/` (with the same path-traversal check
already performed via `7z l`), then inspect the extracted directory structure
(participant/session/segment layout, label files, synchronization metadata,
and the official code's `environment.yml`/`requirements.txt`) against
`docs/leakage_risk_register.md` before any fold design or preprocessing work
begins.
