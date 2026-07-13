# Data Provenance

## Official source

- **Publication:** Scientific Data article — https://www.nature.com/articles/s41597-026-07456-0
- **Dataset host:** Zenodo, record ID `17773125`
- **DOI:** `10.5281/zenodo.17773125`
- **Concept DOI (all versions):** `10.5281/zenodo.17773124`
- **Official API endpoint used:** `https://zenodo.org/api/records/17773125`
  (note: `api.zenodo.org` is not a valid host for this API; see
  `docs/decision_log.md`)
- **License:** `cc-by-4.0` (as declared in the Zenodo record metadata)
- **Version:** `1.0.0`
- **Access:** open

No mirror, third-party redistribution, or unofficial copy is used anywhere in
this project. All acquisition scripts fetch exclusively from `zenodo.org`.

## Chain of custody

1. Official Zenodo JSON record fetched by `scripts/00_fetch_dejavu_zenodo_metadata.py`,
   saved byte-for-byte unmodified to
   `/mnt/HDD/AliWorks/DEJA-VU/metadata/zenodo_record_17773125.json`, with a
   SHA-256 of that exact file recorded in
   `/mnt/HDD/AliWorks/DEJA-VU/checksums/zenodo_record_17773125.json.sha256`.
2. A download manifest (`docs/dejavu_download_manifest.csv`) was generated
   directly from the fields of that JSON record — no filename, size, or
   checksum was typed in or guessed.
3. Each official file is downloaded by `scripts/00_download_dejavu_zenodo.py`
   directly from its `links.self` content URL on `zenodo.org`, streamed to a
   `.part` file under `/mnt/HDD/AliWorks/DEJA-VU/raw_downloads/`, and only
   renamed to its final official filename after its exact byte size and its
   official Zenodo checksum (MD5, as provided by Zenodo) both verify.
4. Independent re-verification is available at any time via
   `scripts/00_verify_dejavu_checksums.py`, which re-reads the same manifest
   and re-hashes the files on disk without trusting any cached "already
   downloaded" state.

## Official files

See `docs/dejavu_source_verification.md` for the full field-by-field record
and `docs/dejavu_download_manifest.csv` for the machine-readable manifest.
Summary:

| Filename | Size | Checksum (MD5) | Category |
|---|---|---|---|
| `DEJA-VU.rar` | 3.72 GiB | `0815b7d78915d132084f4ef497cef6d0` | archive (main dataset) |
| `DEJA_VU_code.rar` | 56.42 KiB | `0747b65d5bbe215c621e435d546fe1c0` | official_code |

## Filename preservation

Official filenames (`DEJA-VU.rar`, `DEJA_VU_code.rar`) are preserved exactly
as published on Zenodo. No renaming, re-encoding, or reformatting is applied
to raw downloaded files at any stage of this pipeline.

## Extraction

**Original attempt (prior session):** the installed `7zip` package
(23.01+dfsg-11, the Debian Free Software Guidelines build) could **list**
RAR/RAR5 archive contents but its RAR decompression codec is removed for
licensing reasons — it could not decompress either archive at all (`ERROR:
Unsupported Method` on every entry). The resulting all-zero-byte output was
removed.

**Continuation stage (2026-07-13):** `unar`/`lsar` were installed (with the
user's explicit help, since it required an interactive `sudo` password).
`DEJA_VU_code.rar` extracted completely (15/15 files). `DEJA-VU.rar`
extracted 269 of 308 files (87.3%) with exact byte-for-byte size match — the
remaining 39 (11 `preprocessed/*.h5`, 28 `segments/**/*.h5`) were
deterministically truncated by `unar`'s RAR5 decoder (reproduced identically
on a repeat single-file extraction; the archive's own MD5 was unaffected).
**All audit-critical files — the 34 raw XDF recordings, the SQLite database,
and the XLSX spreadsheet — extracted 100% correctly.**

**Further continuation stage (2026-07-13):** `unrar` (RARLAB's official
reference implementation, installed after the `unar` truncation but not
retried until now) was used to re-extract the full archive into a fresh
staging directory, achieving **308/308 files, exact size match, 0
anomalies**, verified independently against the complete archive listing and
by opening every HDF5/SQLite/XLSX/XDF file. The validated staging extraction
was atomically swapped in as the canonical `extracted/dataset/`; the prior
partial `unar` output is preserved at
`extracted/dataset_partial_unar_backup/`. Full detail:
`docs/dejavu_extraction_report.md`, `docs/dejavu_unrar_validation_report.md`.

## What has NOT happened

- No raw data, archive, or extracted file has been committed to Git. See
  `.gitignore` for the enforced exclusions.
- No preprocessing, segmentation, labeling, or model training has been
  performed on any DEJA-VU signal data.
