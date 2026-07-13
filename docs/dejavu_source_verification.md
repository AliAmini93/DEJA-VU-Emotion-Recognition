# DEJA-VU Official Source Verification

Source: `https://zenodo.org/api/records/17773125`, fetched via
`scripts/00_fetch_dejavu_zenodo_metadata.py` on 2026-07-13.

Raw response saved unmodified at `/mnt/HDD/AliWorks/DEJA-VU/metadata/zenodo_record_17773125.json`
(5915 bytes), SHA-256 recorded at `/mnt/HDD/AliWorks/DEJA-VU/checksums/zenodo_record_17773125.json.sha256`
(`42a71ea4d172777c610c3e44e8b30ddc760b48b3557f230dd103218442ffb99a`).

All fields below are copied verbatim from the fetched JSON. None are inferred.

## Record identity

| Field | Value |
|---|---|
| Record ID | `17773125` (validated by fetch script: `data["id"] == 17773125`) |
| Concept record ID | `17773124` |
| DOI | `10.5281/zenodo.17773125` |
| Concept DOI | `10.5281/zenodo.17773124` |
| Title | DEJA-VU: A multimodal dataset for emotional transition analysis in virtual reality |
| Publication date | `2025-12-01` |
| Created (Zenodo record) | `2025-12-01T03:08:02.809675+00:00` |
| Updated (Zenodo record) | `2025-12-01T03:08:03.249352+00:00` |
| Version | `1.0.0` |
| Access status | `open` |
| License ID | `cc-by-4.0` |
| Resource type | `dataset` |
| Status | `published` |

## Creators

| Name | Affiliation | ORCID |
|---|---|---|
| Ishmakhametov, Namazbai | Kennesaw State University | 0000-0002-3352-6143 |
| Naser, Mohammad | Kennesaw State University | 0000-0001-9465-351X |
| Kelil, Selam | Kennesaw State University | 0009-0004-6022-0889 |
| McClary, Charles | Kennesaw State University | 0009-0000-2983-0882 |
| Metcalfe, Jason S. | DEVCOM Army Research Laboratory | 0000-0001-9086-9962 |
| Bhattacharya, Sylvia | Kennesaw State University | 0000-0002-5525-7677 |

## Keywords / related identifiers

Both `metadata.keywords` and `metadata.related_identifiers` are `null` in the
Zenodo record as fetched. Not inferred, not fabricated.

## Description (verbatim, as returned by Zenodo)

> Emotion recognition from physiological signals typically treats emotions as
> discrete, static states rather than dynamic processes, creating limitations
> for real-world affective computing applications. This dataset contains
> multimodal physiological recordings from 28 participants experiencing
> systematically designed emotional transitions in virtual reality
> environments. Participants viewed validated emotion-eliciting video stimuli
> across three emotional quadrants with 69-second neutral reset periods
> between stimuli. Four physiological modalities were recorded simultaneously:
> EEG (7 channels, 300 Hz), ECG (4 leads, 512 Hz), EMG (2 channels, 512 Hz),
> and GSR (3 channels, 10 Hz). The experimental protocol employed balanced
> incomplete block design across six possible emotional sequences. Statistical
> validation demonstrates quadrant differentiation with average of 70%
> physiological validation based and 85% self-reported based emotion induction
> success rates. Individual journey analysis reveals emotional mobility
> ranging 8.84%-58.39% on Valence-Arousal plane of theoretical maximum. The
> dataset comprises 1.85GB of raw data and 238 video-aligned physiological
> segments, and comprehensive self-assessment ratings. This resource enables
> research in dynamic emotion recognition, temporal affective computing, and
> individual differences in emotional responsivity during controlled
> emotional transitions.

**Observed discrepancy (documented, not resolved):** the description states
"1.85GB of raw data," but the sum of the two official file sizes on Zenodo is
3,996,579,943 bytes (3.72 GiB) — roughly double. This is not resolved here; it
may reflect compression, inclusion of stimulus video files, packaging of
processed segments alongside raw signals, or a discrepancy in the paper text
itself. It must be re-examined once `DEJA-VU.rar` is extracted and its
contents are enumerated. No fact from the description is used to override or
substitute for the file listing below.

## Official files (exact, from Zenodo `files[]`)

| Filename | Size (bytes) | Size (human) | Checksum |
|---|---|---|---|
| `DEJA-VU.rar` | 3,996,522,166 | 3.72 GiB | `md5:0815b7d78915d132084f4ef497cef6d0` |
| `DEJA_VU_code.rar` | 57,777 | 56.42 KiB | `md5:0747b65d5bbe215c621e435d546fe1c0` |

- **File count:** 2
- **Total bytes:** 3,996,579,943 (3.72 GiB)
- **Checksum algorithm:** MD5 for both files (as provided by Zenodo; this is
  Zenodo's own integrity checksum format, not a SHA-256 — the acquisition
  scripts verify against exactly this algorithm/value pair, they do not
  substitute a different algorithm).
- **Media type:** Zenodo's `files[]` objects for this record do **not** include
  a `type`/media-type field (only `key`, `size`, `checksum`, `links`, `id`).
  No media type is fabricated; it is left blank in the manifest and can only
  be determined from the file extension (`.rar`) or, after extraction, from
  the actual archive contents.
- **Download URLs** (from `links.self` in the record, content endpoint):
  - `https://zenodo.org/api/records/17773125/files/DEJA-VU.rar/content`
  - `https://zenodo.org/api/records/17773125/files/DEJA_VU_code.rar/content`

## Validation performed

- `data["id"] == 17773125` — **PASSED**
- All required top-level fields present (`id, conceptrecid, doi, conceptdoi, created, updated, files`) — **PASSED**
- All required `metadata` fields present (`title, publication_date, version, access_right, license, creators, description`) — **PASSED**
- Every file entry has `key, size, checksum, links` and a well-formed `algorithm:value` checksum string — **PASSED**
- File `size` values are positive integers — **PASSED**

## Category assignment (descriptive only — does not exclude any file)

| Filename | Assigned category | Basis |
|---|---|---|
| `DEJA-VU.rar` | `archive` | `.rar` container; per the record description likely bundles raw physiological recordings + 238 video-aligned segments + self-assessment ratings — exact internal layout unknown until extracted |
| `DEJA_VU_code.rar` | `official_code` | filename explicitly identifies it as the dataset's companion code |

See `docs/dejavu_download_manifest.csv` for the machine-readable manifest built
from this verification, and `docs/dejavu_source_verification.json` for the
structured equivalent of this document.

## Outcome

**Official source: VERIFIED.** Record ID `17773125` confirmed. Metadata is
internally consistent and complete for acquisition planning.
