# DEJA-VU Archive Safety Report

Pre-extraction validation, run via `scripts/00_validate_archive_members.py`
(which uses `scripts/archive_listing.py`) **before any extraction was
attempted**. This supplements the `7z l` path-traversal check already
performed in the prior acquisition stage with explicit, automated checks for
a wider set of unsafe conditions.

## Listing tool used

Initially produced via `7z l` (the DFSG 7zip build can list RAR/RAR5
archives; it just cannot decompress them — see
`docs/dejavu_acquisition_report.md`), before `unar`/`lsar` were installed.
After installation (`docs/archive_extractor_environment.md`), both archives
were **re-listed and re-validated with `lsar -json`**, which — unlike `7z
l` — exposes an explicit `XADIsLink` field, giving a genuine (not
best-effort) symlink check. Results were identical: 0 issues in both
archives. Final listings saved to:

- `/mnt/HDD/AliWorks/DEJA-VU/metadata/DEJA-VU_archive_listing.txt` (lsar `-l` output, 441 lines)
- `/mnt/HDD/AliWorks/DEJA-VU/metadata/DEJA_VU_code_archive_listing.txt` (lsar `-l` output, 21 lines)

## Validation checks performed

For every archive member, `scripts/00_validate_archive_members.py` checks:

1. Embedded null characters in the path — **rejects**.
2. Absolute paths (leading `/`, `\`, or a drive letter) — **rejects**.
3. A literal `..` path component — **rejects**.
4. The path resolving outside the extraction root once joined (via
   `dejavu_lib.safe_join`, the same tested function used by the downloader) — **rejects**.
5. Duplicate normalized paths (after separator normalization) — **rejects**.
6. Case-collision paths — two distinct archive members that would collide on
   a case-insensitive filesystem (macOS/Windows) even though this machine's
   ext4 filesystem is case-sensitive — **rejects**, for portability safety.
7. Symlink members, if the listing tool flags them — **rejects** (none were
   flagged by `7z l`, which does not reliably expose link attributes for RAR
   archives; this is a known limitation of the fallback tool, noted rather
   than glossed over).

## Results (final, via lsar)

| Archive | Members listed | Files | Directories | Issues found | Result |
|---|---|---|---|---|---|
| `DEJA_VU_code.rar` | 16 | 15 | 1 | 0 | **VALIDATION PASSED** |
| `DEJA-VU.rar` | 436 | 308 | 128 | 0 | **VALIDATION PASSED** |

No archive member in either file triggered any of the seven checks above,
under either tool. Both archives are confirmed safe to extract into their
respective destinations (`extracted/official_code/`, `extracted/dataset/`).
