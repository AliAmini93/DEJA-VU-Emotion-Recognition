# Project Status — Current

Last updated: 2026-07-13 (Europe/Vilnius)

## Phase

**Data-Only Audit.** No modeling, preprocessing, or training has occurred.

## Stage status

| Stage | Status |
|---|---|
| Stage 0 — Environment | COMPLETE: shared venv verified, pre/post snapshots taken, missing audit dependencies installed with zero protected-core-package changes, `pip check` passed, PyTorch+CUDA re-validated. |
| Stage 1 — Source verification | COMPLETE: official Zenodo record `17773125` fetched, checksummed, and field-validated. 2 official files identified, 3.72 GiB total. |
| Stage 2 — Acquisition | COMPLETE (download + checksum verification, 0 failures). |
| Stage 2b — Extraction (continuation stage, 2026-07-13) | PARTIAL: `unar`/`lsar` installed; code archive 15/15 complete; main archive 269/308 files (87.3%) exact-match, 39 HDF5 files (preprocessed/segment only) truncated by a deterministic `unar` decoder limitation. **All audit-critical files (34 raw XDF, database, spreadsheet) are 100% complete.** See `docs/dejavu_extraction_report.md`. |
| Stage 3 — Structural audit (continuation stage) | See `docs/data_audit_dejavu.md`, `docs/dejavu_identity_conflict_audit.md`, `docs/dejavu_trial_unit_preliminary_audit.md`. |

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

- **39 of 308 files in the main archive remain truncated** (11
  `preprocessed/*.h5`, 28 `segments/**/*.h5`) — `unar`'s RAR5 decoder fails
  deterministically on these specific files. The user was asked whether to
  install `unrar` as a targeted fallback; see `docs/decision_log.md` for the
  current state of that request. None of these 39 files are required for the
  identity-conflict audit or trial-unit analysis.
- No `configs/` or `folds/` content has been created — these depend on the
  leakage risk register being substantially addressed first, which in turn
  depends on a full (not just structural) content audit of all physiological
  signal files, including the 39 currently truncated ones.

## Next permitted action

If the user installs `unrar`, retry extraction of the 39 remaining truncated
files specifically, then re-run `scripts/01_audit_dejavu_dataset.py` to
extend the structural audit to their content. Independently of that: proceed
to a deeper per-channel physiological signal quality audit (SNR, artifact
rate) using the already-complete raw XDF files and the 269 already-verified
HDF5 files, before any fold design or preprocessing work begins.
