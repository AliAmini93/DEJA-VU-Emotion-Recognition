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

## 2026-07-13 — Zenodo maintenance window observed during prior audit

The prior environment audit observed `zenodo.org` returning HTTP 503 with a
self-reported scheduled-maintenance banner. `api.zenodo.org` does not exist as
a host (NXDOMAIN); the correct REST API path is `https://zenodo.org/api/records/{id}`.
This project's metadata-fetch script (`scripts/00_fetch_dejavu_zenodo_metadata.py`)
uses the correct `zenodo.org/api/records/...` path and treats HTTP 503 /
connection failure as a retryable, then ultimately reportable, condition — not
as evidence that the record does not exist.
