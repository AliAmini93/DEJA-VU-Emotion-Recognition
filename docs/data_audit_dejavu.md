# DEJA-VU Structural Data Audit

Produced by `scripts/01_audit_dejavu_dataset.py` (read-only; no
preprocessing, no signal analysis, no model training). Full structured
output: `docs/data_audit_dejavu.json`. Per-entity CSVs:
`docs/dejavu_file_inventory.csv`, `docs/dejavu_subject_session_summary.csv`,
`docs/dejavu_channel_inventory.csv`, `docs/dejavu_event_inventory.csv`.

## Directory layout (extracted, verified files only)

**Updated 2026-07-13 (further continuation stage): the `unrar` re-extraction
achieved 308/308 exact-size matches (see `docs/dejavu_extraction_report.md`);
all counts below now reflect content inspection of the complete dataset, not
the earlier 269/308 `unar` partial state.**

```
extracted/dataset/DEJA-VU/
├── data.xlsx                    (spreadsheet, complete)
├── deja_vu_database.db          (SQLite, complete)
├── preprocessed/                (34 files, 100% complete)
│   └── clean_P0##_S00#.h5
├── raw/                         (34 files, 100% complete)
│   └── sub-P0##/ses-S00#/eeg/*.xdf
└── segments/                    (238 files, 100% complete)
    └── sub-P0##/S00#_{neutral_baseline,quadrant_*,transition_*_period}.h5
```

## SQLite database (`deja_vu_database.db`) — read-only inspection

12 tables:

| Table | Rows | Columns |
|---|---|---|
| `videos` | 510 | subject, session, video_order, video_name, video_start_24, time_abs, time_rel |
| `journey` | 136 | subject, session, position, video_name, quadrant, video_order |
| `video_mappings` | 19 | video_name, source, emotion, quadrant, length_mmss, length_sec |
| `session_metadata` | 34 | date, subject, session, start_time, temp_inside, room_lighting, sleep, stimulant, activity, permutation |
| `ratings` | 272 | subject, session, video_name, quadrant, rating_time, rating_valence, rating_arousal, rating_dominance |
| `keys` | 28 | subject, ses1, ses2 |
| `scores_big_five` | 28 | subject, extraversion, agreeableness, conscientiousness, neuroticism, openness |
| `scores_panas` | 68 | subject, session, status, positive_affect, negative_affect |
| `survey_big_five` | 1400 | subject, question, answer |
| `survey_panas` | 1360 | subject, session, status, question, answer |
| `survey_ekman` | 204 | subject, session, emotion, video_a, video_b, video_c |
| `survey_screener` | 56 | subject, question, answer |

**28 distinct subjects** (`P001`–`P028`), **34 distinct (subject, session)
pairs** — matching the official code's "34 sessions" exactly (6 subjects
have 2 sessions: confirmed 34 − 28 = 6 second-sessions).
`videos` (510 rows) ÷ 34 sessions ≈ 15 events/session (4 journey + 8 SAM + 3
Baraka), matching `validate_session()`'s expected counts.

## XLSX workbook (`data.xlsx`) — read-only inspection

9 sheets, headers read (no full-column values loaded beyond header row):
`keys`, `survey_screener`, `survey_big_five`, `survey_panas`,
`survey_ekman`, `session_metadata`, `videos`, `ratings`, `video_mappings` —
names and row/column counts closely mirror the SQLite tables (e.g. `videos`:
511 rows incl. header ≈ 510 DB rows + 1). The spreadsheet appears to be the
same underlying data as the database, in a second format — not independently
verified row-by-row in this pass (out of scope for a structural audit).

## Raw XDF files — 34/34, 100% complete

All 34 raw recordings parsed successfully via `pyxdf` (arrays discarded
immediately after metadata extraction — no signal data retained in any
output file). Each contains exactly 4 LSL streams:

| Stream | Modality | Channels (raw) | Rate | Notes |
|---|---|---|---|---|
| `DSI_FLEX` | EEG | 8 (`F3,S2-S7,TRG`) | 300 Hz | `TRG` excluded by code; 7 EEG/EOG channels remain |
| `Shimmer_894F` | GSR + accel + PPG | 7 (`Accel_X/Y/Z, GSR_Skin_Resistance, GSR_Skin_Conductance, GSR_Range, PPG_A13`) | ~10 Hz | code keeps only channel index 0 — see below |
| `Shimmer_BBBD` | EMG + battery/status | 4 (`Battery, ECG_EMG_Status1, EMG_CH1_24BIT, EMG_CH2_24BIT`) | 512 Hz | code keeps channels 2–3 as EMG |
| `Shimmer_BE1D` | ECG + accel/status | 9 (`Accel_X/Y/Z, ECG_EMG_Status1/2, ECG_LL-RA,LA-RA,LL-LA,Vx-RL`) | 512 Hz | code keeps channels 0–3 — see below |

**Channel-order discrepancy (dataset-wide, verified in 2 independent files):**
the official code's assumed channel indices for ECG and GSR do not match the
true labeled positions in the raw stream (true ECG leads are at indices 5–8,
not 0–3; true GSR conductance is at index 4, not 0). Logged as leakage risk
#9, sub-finding B — **OPEN**, unresolved, not fixed by this audit.

## Preprocessed HDF5 (`preprocessed/*.h5`) — 34/34 inspected, 100% complete

Structure (from `lib_preprocessing_utils.py::save_preprocessed_hdf5`, cross-
checked against real files): top-level attrs `subject_id, session_id,
original_xdf, processing_date, report`; one group per modality
(`eeg,ecg,emg,gsr`) each with `data`, `timestamps` datasets and
`sampling_rate, channels` attrs. Confirmed channel lists match the code's
documented mapping (EEG → `FP1,FP2,C3,C4,LE,EOG1,EOG2`; ECG →
`ECG_Lead_I..Chest`; EMG → `EMG_Zygomaticus,EMG_Trapezius`; GSR →
`GSR_Conductance`). Full inventory: `docs/dejavu_channel_inventory.csv`
(1083 rows incl. header, 4 modality rows × 272 HDF5 files — now all
272, not the 233 available at the prior `unar`-partial checkpoint).

## Segment HDF5 (`segments/**/*.h5`) — 238/238 inspected, 100% complete

Structure: per-modality groups (as above) plus a `segment_info` group with
attrs `type, subject, session, quadrant, video_name, start_time, end_time,
duration`, and for transitions, `transition_type`. Every inspected file's
`segment_info.subject`/`session` matches its containing `sub-P0##/` folder —
**all 272 HDF5 files checked (34 preprocessed + 238 segments), 0
subject/session mismatches found** between folder path and internal
`segment_info`/top-level attrs (the one apparent mismatch in the whole
dataset is the raw XDF *filename* audited separately in
`docs/dejavu_identity_conflict_audit.md`, which the segment/preprocessed
pipeline itself does not inherit — confirmed again now with full coverage,
not just the 233-file partial check from the prior stage). Full inventory:
`docs/dejavu_event_inventory.csv`.

## Subject/session summary

See `docs/dejavu_subject_session_summary.csv` for the full per-participant
breakdown. Headline: **28 independent participants**, **34 participant-
sessions** (22 participants with 1 session, 6 with 2 sessions — matches
`docs/dejavu_official_code_audit.md`'s code-derived expectation exactly).

## Outcome

**Dataset structural audit: COMPLETE for all 308 files** (34 raw XDF, 34
preprocessed HDF5, 238 segment HDF5, 1 SQLite database, 1 XLSX workbook) —
no file skipped, none truncated. This supersedes the prior checkpoint's
partial coverage (233/272 HDF5 files), which is preserved for the historical
record in earlier revisions of this document and in
`docs/dejavu_extraction_report.md`.
