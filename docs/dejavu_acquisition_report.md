# DEJA-VU Acquisition Report

Run: 2026-07-13, via `scripts/00_download_dejavu_zenodo.py` (two invocations —
see the manifest-path bug note in `docs/decision_log.md`) followed by
independent verification via `scripts/00_verify_dejavu_checksums.py`.

## Pre-flight

| Check | Value |
|---|---|
| Total official bytes | 3,996,579,943 (3.72 GiB) |
| Free space at start | 474.87–475.62 GiB |
| Required headroom | total + 20 GiB |
| Pre-flight result | PASSED |

## Downloader summary (final run)

```
total_expected_bytes: 3996579943 (3.72 GiB)
downloaded_bytes: 3996579943 (3.72 GiB)
verified_bytes: 3996579943 (3.72 GiB)
remaining_bytes: 0 (0.00 B)
total_files: 2
successful_files: 2
failed_files: 0
resumed_files: 1
checksum_failures: 0
```

`DEJA_VU_code.rar` completed and verified on the first run.
`DEJA-VU.rar` was interrupted mid-download (811,597,824 of 3,996,522,166 bytes
written) due to a manifest-path bug caught and fixed live (see
`docs/decision_log.md`); the second run correctly resumed via HTTP `Range:
bytes=811597824-`, the server returned `206 Partial Content`, and the
remaining bytes were streamed and appended to the existing `.part` file — no
data was re-downloaded or lost.

## Independent checksum re-verification

Run separately via `scripts/00_verify_dejavu_checksums.py` (does not trust the
downloader's own "already verified" state — re-reads and re-hashes both files
from disk):

| Filename | Size match | Checksum match | Status |
|---|---|---|---|
| `DEJA-VU.rar` | YES (3,996,522,166 / 3,996,522,166) | YES (md5) | VERIFIED |
| `DEJA_VU_code.rar` | YES (57,777 / 57,777) | YES (md5) | VERIFIED |

Full machine-readable report: `docs/dejavu_checksum_report.csv`.

## Manual MD5 spot-check

```
$ md5sum raw_downloads/DEJA-VU.rar raw_downloads/DEJA_VU_code.rar
0815b7d78915d132084f4ef497cef6d0  DEJA-VU.rar
0747b65d5bbe215c621e435d546fe1c0  DEJA_VU_code.rar
```

Both match the official Zenodo `checksum` field exactly.

## Extraction — ATTEMPTED, FAILED, documented honestly (rule #18)

Both archives were first listed with `7z l` to check for path traversal
(absolute paths, `..` components) **before** any extraction was attempted.
None were found in either archive — all 308+15 entries use safe relative
paths under `DEJA-VU/` or `code/`. `DEJA-VU.rar` lists as 308 files / 128
folders, 5,751,558,349 bytes uncompressed, organized as:

- `DEJA-VU/data.xlsx` — spreadsheet (self-assessment ratings, per record description)
- `DEJA-VU/deja_vu_database.db` — SQLite database
- `DEJA-VU/preprocessed/clean_P0{01..28}_S00{1,2}.h5` — ~~35~~ **34** preprocessed HDF5 files (corrected 2026-07-13, see below)
- `DEJA-VU/raw/sub-P0{01..28}/ses-S00{1,2}/eeg/*.xdf` — ~~131~~ **34** raw XDF recordings (corrected 2026-07-13, see below)
- `DEJA-VU/segments/...` — ~~267~~ **238** entries (video-aligned physiological segments, per record description; corrected 2026-07-13)

`DEJA_VU_code.rar` lists 15 files under `code/`: preprocessing, segmentation,
SNR/SAM/journey analysis, and figure-generation scripts, `config_final.py`,
`environment.yml`, `requirements.txt`, and `readme.docx`.

**Extraction itself then failed for every single file in both archives** —
`7z x` reported `ERROR: Unsupported Method` for all 15 files in
`DEJA_VU_code.rar` and all 308 files in `DEJA-VU.rar` (0 successes, 0 bytes of
real content, only a 0-byte-file skeleton written). Root cause identified:
the only archiver installed on this machine is the `7zip` Debian package
(`7zip 23.01+dfsg-11` — the `+dfsg` suffix marks the Debian Free Software
Guidelines build, which has the RAR decompression codec's actual algorithm
removed for licensing reasons). This build can **list** RAR/RAR5 archive
contents (used above for the path-traversal check) but **cannot decompress**
them. `unrar` (non-free, from RARLAB) and `unar` (free, DFSG-compatible,
RAR5-capable) are both available as `apt` candidates but neither is
installed, and installing packages is out of scope for this phase ("do not
install... system packages").

The resulting all-zero-byte extraction output was recognized as invalid,
removed, and `/mnt/HDD/AliWorks/DEJA-VU/extracted/` was restored to empty.
**The raw downloaded `.rar` files were never touched by the failed
extraction** — both were re-verified by MD5 after the extraction attempt and
still match the official Zenodo checksums exactly (see checksum table above).

Because extraction failed, `code/environment.yml` and `code/requirements.txt`
could **not** be inspected. No dependency was added to this project based on
"official code demonstrated requirement" (section 9 of the acquisition
instructions) — the dependency decisions in
`docs/environment_import_validation.md` are based solely on the standard
audit package list, not on inspection of the official code, and this
limitation is stated here explicitly rather than silently glossed over.

## Observed anomaly — documented, not resolved or modified

One raw filename does not match its own directory path:

```
DEJA-VU/raw/sub-P017/ses-S002/eeg/sub-P666_ses-S001_task-Default_run-001_eeg.xdf
```

The file lives under participant `P017`, session `S002`, but its filename
encodes participant `P666`, session `S001`. Participant `P666` does not
appear anywhere else in the archive and is not one of the 28 enrolled
participants. This looks like a leftover placeholder/test identifier from
data collection that was not renamed before packaging by the dataset
authors. **This file has not been renamed, and no raw file has been
modified** — non-negotiable rules #8 and #9 (do not modify raw files,
preserve official filenames) apply to what we do with the file, not to
what the original authors did when naming it. This is logged in
`docs/leakage_risk_register.md` as a synchronization/identity risk to
resolve before this file is used in any per-subject split.

## Size discrepancy re-examined

`docs/dejavu_source_verification.md` flagged that the Zenodo description says
"1.85GB of raw data" while the total archive download is 3.72 GiB. **With
the archive listed but not extracted at that checkpoint**, the `raw/`
directory alone (34 `.xdf` files, corrected count — see below) sums to well
under 2 GiB, consistent with "1.85GB of raw data" referring specifically to
the `raw/` subdirectory — the remaining size comes from `preprocessed/` (34
HDF5 files) and `segments/` (238 entries), which the description separately
calls out as "238 video-aligned physiological segments." This resolves the
apparent discrepancy without needing to assume anything not directly
observed in the listing.

## Outcome (as of this stage's original checkpoint)

**Download: COMPLETE.** **Checksum verification: COMPLETE, 0 failures.**
**Extraction: FAILED** (no RAR5-capable decompressor installed; listing-only
`7zip+dfsg` cannot decompress; fix requires installing `unar` or `unrar`,
which was out of scope for that phase). `extracted/` was empty.
`raw_downloads/` was unaffected and both official files remained
checksum-verified on disk.

---

## 2026-07-13 (continuation stage) — Extraction retried and mostly succeeded

This section is added, not a rewrite of the above — the original failure and
its cause stand as documented.

1. **Earlier failure (recap):** `7zip+dfsg` could list but not decompress
   either RAR/RAR5 archive.
2. **Installation:** `unar`/`lsar` 1.10.1 were installed this stage (required
   an interactive `sudo` password the automated session could not supply;
   the user ran the install themselves — see
   `docs/archive_extractor_environment.md`).
3. **Re-extraction:** `DEJA_VU_code.rar` → `extracted/official_code/`
   **succeeded completely** (15/15 files, exact size match). `DEJA-VU.rar` →
   `extracted/dataset/` **succeeded partially**: 269 of 308 files (87.3%)
   extracted with exact byte-for-byte size match; 39 files (11 preprocessed
   HDF5, 28 segment HDF5) were deterministically truncated by `unar`'s RAR5
   decoder (reproduced identically on a repeat attempt; archive MD5
   unaffected). **All audit-critical files — the 34 raw XDF recordings, the
   SQLite database, and the XLSX spreadsheet — extracted 100% correctly.**
   Full detail: `docs/dejavu_extraction_report.md` / `.json`.
4. **Verification method:** every one of the 308 archive entries (not just
   the 39 `unar` flagged) was independently checked against its
   `lsar -json`-reported size; zero-byte files, path escapes, and archive
   MD5 drift were all explicitly checked and ruled out.
5. **Final extracted counts and sizes:** 269/308 files, 5,746,209,639 of
   5,751,558,349 expected bytes (5,348,710 bytes short, exactly accounted for
   by the 39 known truncations).
6. **Correction of miscounts from the original checkpoint above:** this
   report originally stated "131 raw XDF recordings," "35 preprocessed HDF5
   files," and "267 segments." All three were **wrong** — that session
   viewed only a truncated slice of the archive listing. The
   listing-derived, now fully verified counts are **34 raw XDF, 34
   preprocessed HDF5, 238 segments** (34 sessions × 7 segments/session,
   which also matches the official code's own "Orchestrates Level 1
   segmentation for all 34 sessions" and `expected_files = len(successful) * 7`
   — see `docs/dejavu_official_code_audit.md`).

## Outcome (current, supersedes the section above where they conflict)

**Download: COMPLETE.** **Checksum verification: COMPLETE, 0 failures.**
**Extraction: PARTIAL** — code archive complete (15/15); main archive 269/308
files (87.3%), all audit-critical files (raw XDF, database, spreadsheet)
100% complete, 39 HDF5 files (preprocessed/segment only) truncated by a
`unar` decoder limitation, disposition tracked in
`docs/dejavu_extraction_report.md`. `raw_downloads/` remains unaffected and
both official archive files remain checksum-verified on disk throughout.
