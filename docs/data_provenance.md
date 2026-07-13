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

The installed `7zip` package (23.01+dfsg-11, the Debian Free Software
Guidelines build) can **list** RAR/RAR5 archive contents but its RAR
decompression codec is removed for licensing reasons — it **cannot actually
decompress** either official archive. Extraction was attempted and failed for
all 323 files across both archives (`ERROR: Unsupported Method` from `7z x`
on every entry). The resulting invalid, all-zero-byte output was removed;
`extracted/` is empty. Fixing this requires installing `unar` (free,
DFSG-compatible, RAR5-capable) or `unrar` (non-free), which is out of scope
for this phase. Full detail in `docs/dejavu_acquisition_report.md`.

## What has NOT happened

- The official archives have not been extracted (see above).
- No raw data, archive, or extracted file has been committed to Git. See
  `.gitignore` for the enforced exclusions.
- No preprocessing, segmentation, labeling, or model training has been
  performed on any DEJA-VU signal data.
