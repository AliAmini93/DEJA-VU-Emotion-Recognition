# DEJA-VU Extraction Report

Extraction tool: `unar` 1.10.1 (installed this stage; see
`docs/archive_extractor_environment.md`). Both archives were validated for
path safety first (`docs/dejavu_archive_safety_report.md`, 0 issues).

## Code archive — `DEJA_VU_code.rar` → `extracted/official_code/`

**COMPLETE.** All 15 files extracted, each verified to match its
archive-listed size exactly, 0 zero-byte files, no path escapes. Log:
`/mnt/HDD/AliWorks/DEJA-VU/logs/extract_code_archive.log`. See
`docs/dejavu_official_code_audit.md` for content inspection.

## Main archive — `DEJA-VU.rar` → `extracted/dataset/`

**PARTIAL — documented honestly, not glossed over.** Log:
`/mnt/HDD/AliWorks/DEJA-VU/logs/extract_dataset_archive.log` (`unar` exit
code 1: *"Extraction ... failed (39 files failed.)"*).

### What actually happened

`unar` reported `Failed! (Attempted to read more data than was available)`
for 39 of 308 files. Every one of the 39 files still exists on disk (no
zero-byte files) but is **genuinely truncated** — confirmed by comparing
on-disk size against the archive-listed size for **all 308 files**, not just
the 39 unar flagged:

| Category | Total in archive | Extracted, exact size match | Truncated |
|---|---|---|---|
| `raw_xdf` (`.xdf` under `raw/`) | 34 | **34 (100%)** | 0 |
| `sqlite_database` (`deja_vu_database.db`) | 1 | **1 (100%)** | 0 |
| `spreadsheet` (`data.xlsx`) | 1 | **1 (100%)** | 0 |
| `preprocessed_hdf5` (`preprocessed/*.h5`) | 34 | 23 | 11 |
| `segment_file` (`segments/**/*.h5`) | 238 | 210 | 28 |
| **Total** | **308** | **269 (87.3%)** | **39 (12.7%)** |

The truncation amounts are small relative to file size (24,190–397,214
missing bytes out of multi-megabyte files) but are real and were re-verified
byte-for-byte, not just trusted from the `unar` log.

### Root-cause investigation performed

1. Re-ran `unar` on a single failed file (`clean_P003_S001.h5`) in isolation
   to a fresh directory: **reproduced the identical truncated size**
   (63,700,992 bytes both times) — this is a **deterministic** decoder
   behavior, not a transient I/O glitch or disk issue.
2. Compared `lsar -json` compression metadata (`RAR5CompressionMethod`,
   `RAR5CompressionInformation`, `RAR5DictionarySize`) between failed and
   successful files of similar size: **identical** compression parameters in
   both cases. No detectable archive-side property distinguishes the 39
   failing files from the 269 succeeding ones.
3. The original archive's MD5 was re-verified **unchanged**
   (`0815b7d78915d132084f4ef497cef6d0`) after the failed extraction attempt —
   the archive itself is intact; this is a limitation of `unar`'s RAR5
   decoder on these specific files, not archive corruption.

### Disposition

The 39 truncated files were **left in place, unmodified**, at their
truncated size — not deleted, not silently treated as valid. They are marked
`size_match=False` / truncated in
`docs/dejavu_extracted_file_inventory.csv`. Per the project's own escalation
rule ("do not install `unrar` unless `unar` installation or extraction
demonstrably fails"), this constitutes exactly that condition. The user was
asked whether to install `unrar` (RARLAB's reference implementation, more
likely to handle this correctly) as a fallback for just these 39 files; see
`docs/decision_log.md` for the outcome of that request.

**None of the 39 truncated files are required for the identity-conflict audit
or the trial/segment-count analysis** — those rely on the (fully correct) raw
XDF files, the database, and code-level evidence. They would matter for a
later, full physiological-signal audit of preprocessed/segment HDF5 content.

## Verification performed on all 308 entries

1. Extraction command exit status recorded (1, due to the 39 failures — not
   swallowed or ignored).
2. Every regular file's existence checked: 308/308 exist.
3. Every regular file's exact byte size compared against the archive
   listing: 269 match exactly, 39 do not (see table above).
4. Zero-byte file check: **0 zero-byte files** (ruling out the earlier
   catastrophic 7z-based failure mode from the prior stage).
5. Path-escape check: all 308 extracted paths resolve inside
   `extracted/dataset/` (verified via the same containment check used by
   `dejavu_lib.safe_join`).
6. Total extracted bytes: 5,746,209,639 of an expected 5,751,558,349
   (5,348,710 bytes short — exactly the sum of the 39 truncation gaps).
7. Original archive MD5 re-verified unchanged after extraction:
   `0815b7d78915d132084f4ef497cef6d0`.
8. Readability: all 269 exact-match files opened successfully in their
   respective format-specific inspection (see `docs/data_audit_dejavu.md`);
   the 39 truncated files were **not** opened for content inspection (their
   HDF5 container structure cannot be trusted while truncated).

## Correction to prior counts (honesty, not silent revision)

The prior acquisition-stage report (`docs/dejavu_acquisition_report.md`, from
the previous session) stated "131 raw XDF recordings" and "35 preprocessed
HDF5 files." **Both were miscounts** — that session viewed only a truncated
`head -80` slice of the archive listing and extrapolated incorrectly. The
correct, now-verified-from-a-complete-listing counts are **34 raw XDF files**
and **34 preprocessed HDF5 files** (one of each per session; 34 sessions
total, matching the official code's own "34 sessions" and the Zenodo
description's "238 video-aligned physiological segments" = 34 × 7). This
correction is applied in `docs/dejavu_acquisition_report.md` with the
original wrong numbers struck through and explained, not deleted — see that
file and `docs/decision_log.md`.

## Outcome

**Main archive extraction: PARTIAL** (269/308 files, 87.3%; all
audit-critical files — raw XDF, database, spreadsheet — are 100% complete).
**Extraction command exit status: FAILURE (1), reported honestly.**
