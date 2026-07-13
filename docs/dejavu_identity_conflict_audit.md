# DEJA-VU Identity Conflict Audit — `sub-P666` filename anomaly

Subject file:
```
DEJA-VU/raw/sub-P017/ses-S002/eeg/sub-P666_ses-S001_task-Default_run-001_eeg.xdf
```

**File has not been renamed, moved, or modified.** This audit only reads
evidence from multiple independent sources and classifies the anomaly; it
does not touch the raw file, per non-negotiable rule #13.

## Evidence gathered

### 1. Directory path

`sub-P017/ses-S002/` — asserts participant P017, session S002.

### 2. Filename

`sub-P666_ses-S001_task-Default_run-001_eeg.xdf` — asserts participant
P666, session S001. **P666 is not one of the 28 enrolled participants**
(confirmed: `SELECT DISTINCT subject FROM videos` in the official database
returns exactly `P001`–`P028`, no `P666`).

### 3. XDF internal stream metadata

Parsed via `pyxdf.load_xdf` (`scripts/01_audit_dejavu_dataset.py`). The file
contains 4 streams — identical in kind, channel layout, and structure to
every other (normally-named) recording in the dataset (cross-checked
directly against `sub-P001_ses-S001..._eeg.xdf`):

| Stream | Type | Channels | Rate | Samples | Duration |
|---|---|---|---|---|---|
| `DSI_FLEX` | EEG | 8 (`F3,S2-S7,TRG`) | 300 Hz | 366,287 | 1221.0 s |
| `Shimmer_894F` | GSR+accel+PPG | 7 | ~10 Hz | 12,209 | 1220.9 s |
| `Shimmer_BBBD` | EMG+battery/status | 4 | 512 Hz | 624,311 | 1221.2 s |
| `Shimmer_BE1D` | ECG+accel/status | 9 | 512 Hz | 624,961 | 1221.0 s |

No stream carries any embedded subject/session identifier (LSL XDF streams
here store device/sensor names, not participant IDs). The recording's
internal structure gives **no signal either confirming or contradicting**
either candidate identity by itself — but it rules out "this is corrupt or
malformed data," since every stream is well-formed and consistent with the
dataset's normal pattern (see "no corruption" below).

### 4. Database records (authoritative, filename-independent)

Queried directly from `deja_vu_database.db` (read-only):

- `session_metadata` has a real, complete row for `(P017, S002)`: date
  `2025-03-19`, start time `1:42:30pm`, permutation `BAC`.
- `journey` has a full, valid 4-position journey for `(P017, S002)`:
  position 1 = `Clouds` (quadrant D, baseline), 2 = `The Shining 2` (B),
  3 = `Fish called Wanda` (A), 4 = `Life is beautiful` (C).
- `videos` has exactly 15 rows for `(P017, S002)` — consistent with 4 journey
  videos + 8 SAM + 3 Baraka = 15, the exact pattern `validate_session()`
  checks for a well-formed session.
- `keys` confirms participant P017 completed both `ses1` and `ses2`
  (`yes`/`yes`).
- **`SELECT ... WHERE subject LIKE '%666%'` returns zero rows in every
  table** (`videos`, `journey`, `session_metadata`, `keys`, `ratings`) — the
  string "666" does not appear anywhere in the database.

### 5. Official-pipeline output (direct, strongest evidence)

`clean_P017_S002.h5` (the dataset's own distributed preprocessed output for
this session, verified checksum-intact, not one of the 39 truncated files)
carries these HDF5 top-level attributes:

```
subject_id:  P017
session_id:  S002
original_xdf: D:\Dissertation\...\replication\data\sub-P017\ses-S002\eeg\
              sub-P666_ses-S001_task-Default_run-001_eeg.xdf
```

**This is the dataset authors' own pipeline recording, in its own output
metadata, that it processed exactly this oddly-named file as subject P017,
session S002.** The full literal (Windows) path is preserved, proving beyond
reasonable doubt which raw file was used, and the pipeline never questioned
or re-derived identity from that filename — it used the directory-based
`subject_id`/`session_id` it was called with (per
`docs/dejavu_official_code_audit.md`'s code-level finding that identity is
always directory/database-driven).

Downstream, `segments/sub-P017/S002_quadrant_A_pos3.h5`'s `segment_info`
group has attrs `subject=P017, session=S002, video_name='Fish called Wanda'`
— which matches the database's `journey` entry for `(P017, S002, position 3)`
exactly.

### 6. Chronological / neighboring-file check

`sub-P017/ses-S002/eeg/` contains **exactly one** `.xdf` file (confirmed via
the full archive listing) — there is no second, "normally-named" XDF file in
that folder that this one might be a stray duplicate of. This rules out the
"a leftover halted-session recording was accidentally included alongside the
real one" scenario — there is no sibling to compare against; this **is** the
recording for that session slot.

### 7. No corruption

All 4 streams parsed cleanly with `pyxdf`, non-zero sample counts, plausible
mutually-consistent durations (~1220–1221 s across all 4 streams, i.e. the
streams are properly synchronized to within ~1.2 s of each other) — nothing
about the file's internal structure suggests truncation or corruption.

## Incidental finding (not part of the identity conflict, logged separately)

While comparing this file's stream channel layout to `sub-P001`'s, an
apparent **channel-order discrepancy in the official preprocessing code**
was observed, identical in both files (i.e., dataset-wide, not specific to
this anomaly): `lib_preprocessing_utils.py::read_and_process_xdf` takes
`Shimmer_BE1D`'s **first 4 raw channels** and labels them
`ECG_Lead_I/II/III/Chest`, but the actual channel order in the raw stream is
`Accel_LN_X, Accel_LN_Y, Accel_LN_Z, ECG_EMG_Status1, ...` — the true ECG
lead channels (`ECG_LL-RA_24BIT` etc.) are at indices 5–8, not 0–3. Similarly
for `Shimmer_894F` (GSR): the code keeps only channel index 0
(`Accel_LN_X`), not `GSR_Skin_Conductance` (actual index 4). **This is
reported here as an observed, unresolved discrepancy in the official code's
assumptions about raw channel ordering — not fixed, not re-derived, and out
of scope for this identity-conflict audit** (it affects every session
equally, so it does not bear on P017 vs. P666 specifically). Recorded for
follow-up in `docs/leakage_risk_register.md`.

## Classification

**`PACKAGING_FILENAME_ONLY`**

Justification: five independent lines of evidence (directory structure,
complete and internally consistent database records for P017/S002, the
dataset authors' own pipeline output explicitly recording `subject_id=P017,
session_id=S002` while preserving the literal odd source filename, a
downstream segment file whose stimulus metadata matches the database
exactly, and the absence of any sibling file in the same folder) all agree
that this recording is genuinely participant P017's second session. The
`sub-P666_ses-S001` string is a naming artifact — most plausibly a leftover
placeholder/test identifier from the recording software or a manual renaming
step during data collection that was never corrected before the file was
placed in its (correct) `sub-P017/ses-S002/` folder — with **zero footprint
anywhere else** in the database, the code, or any other file in the archive.

This conclusion is about the **filename string**, not about the recording's
scientific validity — no claim is made here about signal quality; that is
a separate, not-yet-performed audit.

## Action taken

**None on the file itself.** Not renamed, not moved, not modified — per
non-negotiable rules #8, #9, #13. This finding is recorded in
`docs/leakage_risk_register.md` (risk #9) as a documented, resolved-by-
independent-evidence anomaly. Any future code that processes this dataset
should treat this file's identity as `P017`/`S002` (matching the directory,
database, and the original authors' own processed output) and should
**never** parse subject/session identity from a raw XDF filename, consistent
with how the official code itself behaves.
