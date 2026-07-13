# DEJA-VU Emotion Recognition — Data-Only Audit

## Project purpose

This repository reproducibly acquires, verifies, and documents the official
**DEJA-VU** dataset (Ishmakhametov et al., *"DEJA-VU: A multimodal dataset for
emotional transition analysis in virtual reality,"* Scientific Data,
https://www.nature.com/articles/s41597-026-07456-0; Zenodo record
`10.5281/zenodo.17773125`) — multimodal EEG/ECG/EMG/GSR recordings from 28
participants experiencing designed emotional transitions in VR — as
preparation for later cross-subject emotion-recognition research alongside
the existing DEAP/I-DARE work.

## Data-Only Audit restriction (current phase)

This repository is currently in a **Data-Only Audit** phase. The following are
explicitly **out of scope** until this phase is formally closed:

- No model training of any kind.
- No SSI, PM-SSI-DG, LRSC-TTA, Transformer, Mamba, MoE, fusion, or
  hyperparameter search implementation.
- No performance-based fold selection.
- No treating segments as independent trials, and no using segment count as
  statistical sample size.
- No modification of raw downloaded files, and no renaming away from official
  Zenodo filenames.

See `docs/leakage_risk_register.md` for the specific leakage risks tracked
before any modeling work begins, and `docs/decision_log.md` /
`docs/project_status_current.md` for the current state of the audit.

## Paths

| Purpose | Path |
|---|---|
| Code repository (this repo) | `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition` |
| External data root (never committed) | `/mnt/HDD/AliWorks/DEJA-VU` |
| Shared Python environment | `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv` |

DEAP, I-DARE, and DEJA-VU **share one Python environment** — see
`docs/shared_environment_policy.md`. There is intentionally no
`DEJA-VU-Emotion-Recognition/.venv`.

## Environment activation

```bash
source /mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/activate
which python  # must print /mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/python
```

## Metadata fetch command

```bash
python scripts/00_fetch_dejavu_zenodo_metadata.py
```

Fetches `https://zenodo.org/api/records/17773125`, validates it, and writes
the unmodified JSON + its SHA-256 under `/mnt/HDD/AliWorks/DEJA-VU/metadata/`
and `/mnt/HDD/AliWorks/DEJA-VU/checksums/`.

## Download command

```bash
python scripts/00_download_dejavu_zenodo.py
```

Resumable, checksum-verified download of the official files listed in
`docs/dejavu_download_manifest.csv` into
`/mnt/HDD/AliWorks/DEJA-VU/raw_downloads/`. Supports HTTP Range resume, never
overwrites an already-verified file, and never deletes a `.part` file on
Ctrl+C.

## Checksum command

```bash
python scripts/00_verify_dejavu_checksums.py
```

Independently re-verifies every file already in `raw_downloads/` against the
official manifest and writes `docs/dejavu_checksum_report.csv`.

## Prohibitions (enforced by `.gitignore` and process)

- **Never commit raw data.** `data/`, `raw/`, `raw_downloads/`, `extracted/`,
  and all recording-format extensions (`*.xdf`, `*.h5`, `*.hdf5`, `*.edf`,
  `*.fif`, `*.mat`, `*.sqlite`, `*.db`) plus archives (`*.zip`, `*.tar*`,
  `*.rar`, `*.7z`) are git-ignored.
- **Never train a model before the audit is complete.** This phase produces
  documentation, verification scripts, and integrity reports only.

## Tests

```bash
pytest -q
```

Covers metadata validation, checksum verification, safe-path handling, and
resumable-download behavior (Range honored/ignored, existing-file
reverification, checksum mismatch handling) against a local test server — no
network access required to run the test suite.
