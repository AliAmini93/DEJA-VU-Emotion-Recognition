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
| Stage 2b — Extraction, `unar` attempt (2026-07-13) | PARTIAL: 269/308 files (87.3%), 39 HDF5 files deterministically truncated by `unar`'s RAR5 decoder. Superseded — see next row. |
| Stage 2c — Extraction, `unrar` re-extraction (2026-07-13, further continuation) | **COMPLETE: 308/308 files (100%), exact size match, all readable.** `unrar` 7.00 (RARLAB reference implementation) extracted the archive cleanly into a fresh staging directory, validated, then atomically swapped in as the canonical `extracted/dataset/`. Prior partial `unar` output preserved at `extracted/dataset_partial_unar_backup/`. See `docs/dejavu_extraction_report.md`, `docs/dejavu_unrar_validation_report.md`. |
| Stage 3 — Structural audit (continuation stage) | Re-run against the now-complete dataset — see `docs/data_audit_dejavu.md`, `docs/dejavu_identity_conflict_audit.md`, `docs/dejavu_trial_unit_preliminary_audit.md`, `docs/dejavu_raw_channel_mapping_audit.md`. |

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
- **Complete extraction** (`extracted/dataset/`, 308/308 files via `unrar`,
  see `docs/dejavu_extraction_report.md`) and archive-safety/extraction
  scripts (`scripts/archive_listing.py`, `scripts/00_validate_archive_members.py`).
- **Full structural audit** (`scripts/01_audit_dejavu_dataset.py`,
  `docs/data_audit_dejavu.md/json` + 4 inventory CSVs) covering all 308
  files: 34 raw XDF, 34 preprocessed HDF5, 238 segment HDF5, the SQLite
  database, and the XLSX workbook.
- **Official code audit** (`docs/dejavu_official_code_audit.md/json`,
  `docs/dejavu_official_dependency_inventory.csv`).
- **Identity-conflict audit** (`docs/dejavu_identity_conflict_audit.md/json`)
  — the P666 filename anomaly, classified `PACKAGING_FILENAME_ONLY` with
  5 independent corroborating evidence sources.
- **Forensic channel-mapping audit** (`scripts/01_audit_dejavu_channel_mapping.py`,
  `docs/dejavu_raw_channel_mapping_audit.md/json`,
  `docs/dejavu_raw_channel_mapping_by_session.csv`) — **EEG verified correct;
  EMG, ECG, and GSR all confirmed mis-mapped dataset-wide** (all 34 sessions):
  the officially-distributed "ECG"/"EMG"/"GSR" channels are actually
  accelerometer axes, battery voltage, and a constant status byte.
- **Stimulus-presentation and transition manifests**
  (`scripts/02_build_dejavu_manifests.py`,
  `manifests/dejavu_stimulus_presentation_manifest.{csv,parquet}` — 136 rows,
  `manifests/dejavu_transition_manifest.{csv,parquet}` — 102 rows), kept
  strictly separate, both counts validated (not forced) against the database.
- **Label/rating policy audit** (`docs/dejavu_label_rating_policy_audit.md/json`,
  `docs/dejavu_rating_inventory.csv`) — resolves why 272 ratings exist for
  136 presentations (exactly 2 per presentation: before/after); binary label
  policy left explicitly undefined.
- **Stimulus identity audit** (`docs/dejavu_stimulus_definition_audit.md`,
  `docs/dejavu_stimulus_definition_matrix.csv`) — canonical held-out-content
  unit determined to be `video_name`, with its repetition-skew risk
  documented, not hidden.
- **Preliminary data-capacity tables** (`docs/dejavu_presentation_class_support.csv`,
  `docs/dejavu_stimulus_repetition_support.csv`, `docs/dejavu_transition_support.csv`,
  `docs/dejavu_trial_manifest_validation.md/json`) — descriptive only, no
  folds constructed.
- 119-test suite (`tests/`, up from 75) covering safe paths, checksum
  verification, Zenodo metadata validation, download resume/restart/interrupt
  behavior, archive-member validation, participant/session identity parsing,
  HDF5/SQLite/XLSX/XDF structural inspection, atomic directory replacement,
  channel-mapping classification, and manifest construction (including the
  P666 case) — all passing, no network or real dataset required to run them.
- Leakage risk register (`docs/leakage_risk_register.md`) — 11 risks logged;
  the P666 filename anomaly resolved; the ECG/EMG/GSR channel-mapping defect
  added as risk #11, high severity, OPEN.
- Decision log (`docs/decision_log.md`) recording every non-obvious decision
  and honestly-documented bug/gap across both continuation stages.

## What does NOT exist yet

- **The ECG/EMG/GSR channel-mapping defect is not fixed or worked around.**
  No corrected re-extraction of these three modalities from the raw XDF has
  been performed — this audit only characterizes and reports the defect.
- **No binary valence/arousal label policy has been chosen** (deliberately —
  candidate policies are documented in
  `docs/dejavu_label_rating_policy_audit.md`, none selected).
- **No CV folds of any kind exist.** The manifests, stimulus-identity audit,
  and capacity tables are all inputs to a future Joint Subject–Stimulus CV
  design, not the design itself.
- No `configs/` content has been created.
- The prior partial `unar` extraction is preserved for forensic reference at
  `extracted/dataset_partial_unar_backup/` but is not used by any script or
  report.

## Next permitted action

Decide and document the binary valence/arousal label policy (from the
candidates in `docs/dejavu_label_rating_policy_audit.md`, without reference
to class balance or model performance), and separately, decide how to handle
the ECG/EMG/GSR channel-mapping defect (re-derive from raw XDF at the
correct indices vs. excluding these modalities from near-term work) —
**both are prerequisites**, alongside the already-complete stimulus-identity
and capacity audits, **before Joint Subject–Stimulus CV fold construction
begins.**
