# Decision Log

Chronological record of non-obvious decisions made during DEJA-VU project setup.
Newest entries at the bottom.

---

## 2026-07-13 — Local environment audit completed

A full read-only audit of the local machine was performed before any repository
or environment changes (`docs/environment_audit.md` / `.json` /
`python_environment_inventory.csv`). No packages were installed, no data was
downloaded, no environment was created during that audit.

## 2026-07-13 — Shared environment policy overrides the audit recommendation

The environment audit's own recommendation (section 11 of
`docs/environment_audit.md`) was to create a **new, dedicated** virtual
environment for DEJA-VU, isolated from DEAP/I-DARE. This was **explicitly
overridden by the user**: DEAP, I-DARE, and DEJA-VU now share the single
existing environment at `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv`.
Rationale and trade-offs are recorded in `docs/shared_environment_policy.md`.
This decision knowingly accepts increased cross-project dependency coupling in
exchange for reduced disk usage and reuse of an already-working CUDA-enabled
PyTorch install.

## 2026-07-13 — GitHub repository existence vs. content

**Correction to an earlier assumption in the environment audit:** the audit's
internet-access check confirmed that `https://api.github.com/repos/AliAmini93/DEJA-VU-Emotion-Recognition`
returned HTTP 200 with a valid repository JSON object, and concluded the
repository "exists" and is reachable. This is correct as far as it goes, but it
is **not equivalent to the repository containing any commits or files**. A
valid GitHub repository API response proves only that the repository resource
exists on GitHub; it says nothing about branches, commits, or contents.

At clone time (this session), the repository was confirmed to contain exactly
one commit (`7e0da3a Initial commit`, adding only `LICENSE`) on branch `main`.
The repository was therefore effectively empty of project content before this
session's initialization work. This log entry exists specifically to prevent
future confusion between "repository exists" and "repository is initialized."

## 2026-07-13 — Manifest path bug caused a nested `raw_downloads/raw_downloads/` directory

**Failure, documented honestly (rule #18):** the first version of
`docs/dejavu_download_manifest.csv` set `relative_output_path` to
`raw_downloads/DEJA-VU.rar` / `raw_downloads/DEJA_VU_code.rar`. The downloader
(`scripts/00_download_dejavu_zenodo.py`) joins `relative_output_path` onto
`RAW_DOWNLOADS_DIR`, which is already
`/mnt/HDD/AliWorks/DEJA-VU/raw_downloads`. This produced a nested
`raw_downloads/raw_downloads/` directory during the first download attempt.
Caught mid-download (after `DEJA_VU_code.rar` had fully verified and
`DEJA-VU.rar.part` had ~811 MB written). The running process was interrupted
with SIGINT (not SIGKILL, so the `.part` file was not corrupted mid-write),
both files were moved up one directory level, the now-empty nested directory
was removed, and `relative_output_path` in the manifest was corrected to the
bare filename (`DEJA-VU.rar`, `DEJA_VU_code.rar`). No data was lost — the
already-downloaded `.part` bytes were preserved and reused via HTTP Range
resume on the next run, which is the resumability guarantee the downloader
was built to provide.

## 2026-07-13 — Archive extraction failed; documented and cleaned up honestly

**Failure, documented honestly (rule #18):** after both official archives
downloaded and checksum-verified successfully, extraction into
`/mnt/HDD/AliWorks/DEJA-VU/extracted/` was attempted with `7z x` and failed
for **every** file in both archives (323 files total, 0 successes,
`ERROR: Unsupported Method`). Root cause: the only archiver installed on this
machine, `7zip` 23.01+dfsg-11, is the Debian Free Software Guidelines build,
which can list RAR/RAR5 archives (used safely for the pre-extraction
path-traversal check) but has its RAR decompression codec removed for
licensing reasons — it cannot actually decompress RAR content. `unar` and
`unrar` would both fix this but neither is installed, and installing a
package is out of scope for this phase. The resulting invalid, all-zero-byte
extraction output was recognized as garbage and removed; `extracted/` was
restored to empty. The raw downloaded `.rar` files were unaffected by the
failed extraction attempt and were re-verified by MD5 afterward. Full detail:
`docs/dejavu_acquisition_report.md`.

## 2026-07-13 (continuation stage) — sudo blocker resolved by user for `unar` install

`sudo apt update && sudo apt install -y unar` requires an interactive
password; the automated tool session has no TTY to supply one. Per the
safety rules (no bypassing authentication), the user was asked to either run
the install themselves or cache `sudo` credentials via `sudo -v`. The user
ran the install (or equivalent) outside this session; `unar`/`lsar` 1.10.1
were confirmed present immediately afterward. See
`docs/archive_extractor_environment.md`.

## 2026-07-13 (continuation stage) — 39 files deterministically truncated by `unar`; user asked about `unrar` fallback

After installing `unar`, the code archive extracted completely (15/15), but
the main archive extracted only 269 of 308 files with exact size match. The
other 39 (all HDF5: 11 `preprocessed/`, 28 `segments/`) were truncated by
`unar`'s RAR5 decoder — confirmed **deterministic** (re-extracting a single
failed file in isolation reproduced the identical truncated byte count), and
confirmed **not archive corruption** (the archive's own MD5 was unchanged
before and after). All audit-critical files (34 raw XDF, the SQLite
database, the XLSX spreadsheet) extracted 100% correctly and were
unaffected. Per the project's own escalation rule ("do not install `unrar`
unless `unar` demonstrably fails"), this condition was met, so the user was
asked whether to install `unrar` as a targeted fallback for just the 39
files. As with the `unar` install, this requires an interactive `sudo`
password the automated session cannot supply; the user was asked to run it
themselves. Full detail: `docs/dejavu_extraction_report.md`.

## 2026-07-13 (continuation stage) — corrected miscounted file totals from the prior session

The prior session's `docs/dejavu_acquisition_report.md` stated "131 raw XDF
recordings," "35 preprocessed HDF5 files," and "267 segments" based on a
truncated view of the archive listing (`head -80`) rather than the complete
listing. With the archive now (mostly) extracted and the complete listing
parsed programmatically, the correct counts are **34 raw XDF, 34
preprocessed HDF5, 238 segments** (34 + 34 + 238 + 1 database + 1 spreadsheet
= 308, matching the archive total exactly, and 34 sessions × 7
segments/session = 238, matching the official code's own segmentation
logic). The original document was corrected in place with the wrong numbers
struck through and explained, not silently deleted — see
`docs/dejavu_acquisition_report.md` and `docs/dejavu_extraction_report.md`.

## 2026-07-13 — Zenodo maintenance window observed during prior audit

The prior environment audit observed `zenodo.org` returning HTTP 503 with a
self-reported scheduled-maintenance banner. `api.zenodo.org` does not exist as
a host (NXDOMAIN); the correct REST API path is `https://zenodo.org/api/records/{id}`.
This project's metadata-fetch script (`scripts/00_fetch_dejavu_zenodo_metadata.py`)
uses the correct `zenodo.org/api/records/...` path and treats HTTP 503 /
connection failure as a retryable, then ultimately reportable, condition — not
as evidence that the record does not exist.
