# DEJA-VU Official Code Audit

Source: `DEJA_VU_code.rar`, extracted to
`/mnt/HDD/AliWorks/DEJA-VU/extracted/official_code/code/` (15 files, all
verified — see `docs/dejavu_extraction_report.md`). Read-only inspection;
**no official script was executed.**

## Files present (per `code/readme.docx`)

The readme states the full pipeline has scripts numbered `01`–`26`, but only
a subset was included in this archive:

| Category (per readme) | Scripts actually present |
|---|---|
| Category 1 — Database & Analysis (run independently once DB exists) | `16_sam_validation.py`, `18_journey_analysis.py`, `19_create_main_figures.py`, `26_holistic_ekman.py` |
| Category 2 — Sequential processing (must run in order) | `05_run_preprocessing.py` → `07_run_segmentation.py` → `15_run_snr_analysis.py` |
| Category 3 — Library modules | `lib_preprocessing_utils.py`, `lib_segment_builder.py`, `lib_segment_metadata.py`, `lib_utils.py` |
| Configuration | `config_final.py` |
| Documentation | `readme.docx`, `environment.yml`, `requirements.txt` |

Scripts `01_create_database.py`, `02_create_journey_table.py`, and others
implied by the numbering gap are **not included** — the readme states the
database itself is distributed pre-built (`deja_vu_database.db`, "downloaded
from Zenodo or created from data.xlsx"), so the DB-creation code was not
shared, only its output.

## Key findings from code inspection

### Channel definitions (from `lib_preprocessing_utils.py`)

- **EEG** (device: DSI, stream name contains `"DSI"`): raw channels
  `F3, S2, S3, S4, S5, S6, S7` → remapped to `FP1, FP2, C3, C4, LE, EOG1, EOG2`
  (7 channels total, `TRG` explicitly excluded) — matches the Zenodo
  description's "EEG (7 channels, 300 Hz)".
- **ECG** (Shimmer device ID `Shimmer_BE1D`): first 4 channels →
  `ECG_Lead_I, ECG_Lead_II, ECG_Lead_III, ECG_Chest` — matches "ECG (4 leads, 512 Hz)".
- **EMG** (Shimmer device ID `Shimmer_BBBD`): first 2 channels →
  `EMG_Zygomaticus, EMG_Trapezius` — matches "EMG (2 channels, 512 Hz)".
- **GSR** (Shimmer device ID `Shimmer_894F`): code takes only
  **channel index 0** (`GSR_Conductance`) → 1 channel kept in the cleaned
  data. **This does not match** the Zenodo description's "GSR (3 channels,
  10 Hz)" — the raw XDF stream may carry 3 channels, but
  `read_and_process_xdf` only extracts 1. Not resolved here; requires
  inspecting the actual raw XDF stream to confirm the true raw channel
  count (see `docs/data_audit_dejavu.md`).

### Preprocessing parameters (from `config_final.py`)

EEG bandpass 1–100 Hz + 50 Hz notch + ICA (95% components, EOG-guided
exclusion); ECG bandpass 0.5–45 Hz; EMG highpass 20 Hz + rectify + 0.2 s
smoothing; GSR 1 Hz tonic lowpass. Windowing constants: `WINDOW_SIZE = 10.0`
s, `STRIDE = 8.0` s (i.e., overlapping windows, not used for the Level-1
segments described below — these constants appear to belong to a
finer-grained "Level 2" windowing stage not present in this code archive).
`PARTICIPANT_CONFIG['sessions'] = ["S001", "S002"]`.

### Identity assignment — directory- and database-driven, not filename-driven

- `05_run_preprocessing.py::find_sessions_to_process()` enumerates
  participants by listing `sub-P*` **directories** under `DATA_DIR`, and
  sessions by checking `ses-S00{1,2}` **directory** existence — never by
  parsing any filename.
- `lib_preprocessing_utils.py::read_and_process_xdf(subject_id, session_id)`
  receives `subject_id`/`session_id` as **function arguments** (from the
  directory-driven loop above) and locates the XDF file via
  `find_largest_xdf()`, which picks the **largest file by byte size** in
  the folder — filename content is never parsed for identity. The comment
  explicitly anticipates multiple XDF files per folder ("in case there are
  several, for instance halted sessions").
- `save_preprocessed_hdf5()` writes `subject_id`/`session_id` **as passed
  in** (i.e., from the directory path) into the output HDF5's top-level
  attrs — never derived from the source filename.
- `lib_segment_builder.py::process_single_session(conn, subject, session, ...)`
  is driven by `lib_segment_metadata.get_all_sessions(conn)`, which queries
  **the SQLite database** (`SELECT DISTINCT subject, session FROM videos`) —
  again, filename-independent. Every segment HDF5's `segment_info` group
  stores `subject`/`session` attrs sourced from this same DB-driven loop.

**This is the central piece of code-based evidence for the P666 filename
anomaly** (see `docs/dejavu_identity_conflict_audit.md`): nothing in the
official pipeline ever reads subject/session identity from a raw XDF
filename. The filename is not a load-bearing identifier anywhere in the
provided code.

### Trial/segment structure — resolves the "238 segments" question

- `07_run_segmentation.py` header: *"Orchestrates Level 1 segmentation for
  all 34 sessions"*, and computes `expected_files = len(successful) * 7`.
- `lib_segment_builder.py::process_single_session()` extracts exactly
  **7 Level-1 segments per session**: 1 `neutral_baseline` (hardcoded
  `quadrant='D'`, journey position 1) + 3 `quadrant_*` segments (journey
  positions 2–4) + 3 `transition_*_period` segments (between consecutive
  journey positions).
- **34 sessions × 7 segments = 238** — this exactly matches the Zenodo
  record description's "238 video-aligned physiological segments." This is
  now **verified from official code logic**, not assumed.
- A session's "journey" is a sequence of exactly 4 quadrant positions
  (1 baseline `D` + 3 emotional quadrants), queried from a `journey` table;
  `identify_transitions()` builds exactly 3 transitions between them.
  `validate_session()` expects exactly 8 `SAM` (Self-Assessment Manikin
  rating) entries and 3 `Baraka` (neutral nature-documentary reset clips)
  entries per session in the `videos` timeline table — distinct from the 4
  journey/quadrant videos. Transition duration is validated against a
  123–143 s window (~133 s), which does not by itself equal the "69-second
  neutral reset periods" mentioned in the Zenodo description; the two
  numbers describe different things (fixation/reset duration vs. full
  inter-stimulus transition window) and are not reconciled further here.

### Database schema (inferred from SQL in `lib_segment_metadata.py`, not yet directly inspected)

Tables referenced: `videos(subject, session, video_order, video_name,
time_rel)`, `video_mappings(video_name, quadrant, emotion, length_sec)`,
`journey(subject, session, position, video_name, quadrant, video_order)`.
Directly confirmed against the real database in
`docs/data_audit_dejavu.md`/`.json`.

## Dependency decisions

See `docs/dejavu_official_dependency_inventory.csv` for the full per-package
table. Summary: **every package actually imported by the provided processing
code is already installed** in the shared environment except `seaborn` and
`statsmodels`, both used only by analysis scripts (`19_create_main_figures.py`,
`16_sam_validation.py`) that are out of scope for this read-only structural
audit — **neither was installed**, per the instruction to only install
packages essential for reading files during this stage. `neurokit2`,
`dtaidistance`, `fastdtw`, `xgboost`, and `pymatreader` appear in the author's
personal `environment.yml`/`requirements.txt` (a full Windows/Anaconda
development environment including an IDE, linters, and unrelated tooling) but
are **not imported by any of the 15 provided files** — no action taken.

## Outcome

**Official code audit: COMPLETE.** **Official requirements inspected: YES**
(`environment.yml` and `requirements.txt` both read in full;
actual `import` statements cross-checked against both files and against the
shared environment).
