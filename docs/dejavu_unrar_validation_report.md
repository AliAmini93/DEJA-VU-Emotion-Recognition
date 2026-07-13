# DEJA-VU `unrar` Staging Extraction Validation Report

Staging directory: `/mnt/HDD/AliWorks/DEJA-VU/extracted/dataset_unrar_staging`
(created fresh, confirmed empty before extraction; **not** extracted over the
existing partial `extracted/dataset`).

Command (exact, logged with timestamps in
`/mnt/HDD/AliWorks/DEJA-VU/logs/extract_dataset_unrar.log`):

```
unrar x -o- /mnt/HDD/AliWorks/DEJA-VU/raw_downloads/DEJA-VU.rar /mnt/HDD/AliWorks/DEJA-VU/extracted/dataset_unrar_staging/
START_TIME: 2026-07-13T17:18:35+03:00
END_TIME:   2026-07-13T17:18:53+03:00
EXIT_CODE:  0
```

Elapsed: 18 seconds — notably faster than `unar`'s multi-minute run for the
same archive in the prior stage.

`unrar`'s own final line: **`All OK`**. `-o-` (do not overwrite) was used, not
`-o+`, per instructions — with an empty staging directory this had no
practical effect but guarantees no silent overwrite could have occurred.

## Pre-flight

Archive MD5 reverified immediately before extraction:
`0815b7d78915d132084f4ef497cef6d0` — **matches** the expected official value.

## Validation results (every one of the required checks)

| Check | Result |
|---|---|
| Expected regular files (from `lsar -json` listing) | 308 |
| Expected directories (from archive listing) | 128 |
| Every expected file exists in staging | **308/308 — PASS** |
| Every file size exactly matches archive listing | **308/308 — PASS** |
| Unexpected files present (on disk, not in archive listing) | **0 — PASS** |
| Zero-byte files where archive expects non-zero | **0 — PASS** |
| Path escapes (resolved path outside staging root) | **0 — PASS** |
| Symlinks (any, let alone escaping) | **0 — PASS** |
| All HDF5 files open via `h5py.File(..., "r")`, groups/datasets/attrs enumerable | **272/272 — PASS** (34 preprocessed + 238 segment) |
| Full signal datasets loaded into memory during this check | **No** — only `.shape`/`.dtype` accessed via `visititems`, never `[:]` |
| SQLite opens read-only (`file:...?mode=ro`) | **PASS** |
| XLSX opens read-only (`openpyxl load_workbook(read_only=True)`) | **PASS** |
| All 34 XDF files remain readable via `pyxdf.load_xdf` | **34/34 — PASS** |
| Original archive MD5 unchanged after extraction | **PASS** (`0815b7d78915d132084f4ef497cef6d0`) |
| Total extracted bytes vs. archive-listed total | 5,751,558,349 vs. 5,751,558,349 — **exact match** |

Full per-file detail: `docs/dejavu_unrar_file_size_validation.csv` (308 rows,
all `status=OK`).

## Acceptance decision

All required acceptance conditions are met:

- 308/308 regular files exist ✓
- 308/308 exact size match ✓
- 0 unexpected files ✓
- 0 zero-byte anomalies ✓
- 0 format-open failures ✓
- `unrar` exit code 0 (success) ✓

**Staging extraction: ACCEPTED.** Proceeding to atomic replacement of the
partial `unar`-extracted dataset (`docs/dejavu_extraction_report.md`, section
added this stage).
