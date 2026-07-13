# Environment Import Validation

Executed against the shared environment (`/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv`).

| Item | Value |
|---|---|
| Active Python path | `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/python` |
| Python version | 3.12.3 (GCC 13.3.0) |
| Pip path | `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/pip` |

## Import check — before installation

| Package | Import | Version |
|---|---|---|
| numpy | OK | 2.4.4 |
| pandas | OK | 3.0.2 |
| scipy | OK | 1.17.1 |
| sklearn (scikit-learn) | OK | 1.8.0 |
| pyarrow | MISSING | — |
| h5py | OK | 3.16.0 |
| tables | MISSING | — |
| mne | MISSING | — |
| pyxdf | MISSING | — |
| openpyxl | MISSING | — |
| sqlalchemy | MISSING | — |
| requests | MISSING | — |
| httpx | MISSING | — |
| pooch | MISSING | — |
| yaml (PyYAML) | OK | 6.0.3 |
| pytest | MISSING | — |
| torch | OK | 2.11.0+cu128 |
| mat73 | OK | unknown (module has no `__version__`; package reports 0.65 via pip) |

**Missing audit dependencies identified:** `pyarrow, tables, mne, pyxdf, openpyxl, sqlalchemy, requests, httpx, pooch, pytest`
(`pyyaml` was already satisfied by the installed `PyYAML==6.0.3`, so it was not installed.)

## Dry-run install

```
python -m pip install --dry-run pyarrow tables mne pyxdf openpyxl sqlalchemy requests httpx pooch pytest
```

Result: `pip` reported every protected core package (`numpy, pandas, scipy,
scikit-learn, h5py, matplotlib, torch, joblib, tqdm, mat73`) — and their
transitive dependencies such as `matplotlib`, `scipy`, `tqdm` pulled in via
`mne`/`tables` — as **"Requirement already satisfied"** at their existing
versions. The "Would install" list contained only new, previously-absent
packages and their sub-dependencies (`SQLAlchemy, annotated-types, anyio,
blosc2, certifi, charset-normalizer, decorator, et_xmlfile, greenlet, h11, h2,
hpack, httpcore, httpx, hyperframe, idna, iniconfig, lazy-loader,
markdown-it-py, mdurl, mne, msgpack, ndindex, numexpr, openpyxl, platformdirs,
pluggy, pooch, py-cpuinfo, pyarrow, pydantic, pydantic_core, pygments, pytest,
pyxdf, requests, rich, tables, typing-inspection, urllib3`). **No conflict with
any protected core package was proposed.** Installation proceeded.

## Real installation

```
python -m pip install pyarrow tables mne pyxdf openpyxl sqlalchemy requests httpx pooch pytest
```

Result: `Successfully installed` all 10 top-level packages plus 29 transitive
dependencies (full list in `requirements-lock.txt`).

## `pip check`

```
$ python -m pip check
No broken requirements found.
```

**Result: PASSED.**

## PyTorch / CUDA re-validation (after installation)

```python
import torch
print("torch:", torch.__version__)
print("cuda_available:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu:", torch.cuda.get_device_name(0))
```

```
torch: 2.11.0+cu128
cuda_available: True
gpu: NVIDIA GeForce RTX 5090
```

Identical to the pre-installation baseline (`docs/shared_environment_validation.md`).
**Result: PASSED.**

## Protected core package versions — before vs. after

| Package | Before | After | Changed? |
|---|---|---|---|
| numpy | 2.4.4 | 2.4.4 | No |
| pandas | 3.0.2 | 3.0.2 | No |
| scipy | 1.17.1 | 1.17.1 | No |
| scikit-learn | 1.8.0 | 1.8.0 | No |
| h5py | 3.16.0 | 3.16.0 | No |
| matplotlib | 3.10.9 | 3.10.9 | No |
| torch | 2.11.0+cu128 | 2.11.0+cu128 | No |
| joblib | 1.5.3 | 1.5.3 | No |
| tqdm | 4.67.3 | 4.67.3 | No |
| mat73 | 0.65 | 0.65 | No |

**No protected core package was upgraded, downgraded, replaced, or removed.**

## Newly installed packages (DEJA-VU overlay)

| Package | Version |
|---|---|
| pyarrow | 25.0.0 |
| tables | 3.11.1 |
| mne | 1.12.1 |
| pyxdf | 1.17.5 |
| openpyxl | 3.1.5 |
| SQLAlchemy | 2.0.51 |
| requests | 2.34.2 |
| httpx | 0.28.1 |
| pooch | 1.9.0 |
| pytest | 9.1.1 |

Recorded in `requirements-dejavu-overlay.txt`. Full frozen environment (92
packages) recorded in `requirements-lock.txt`.

## Packages intentionally not installed

Per instruction, the following were **not** installed because no downloaded
file or official DEJA-VU code yet demonstrates they are required: `torch`
(already present, not reinstalled), `torchvision`, `torchaudio`, `jupyter`,
`notebook`, `seaborn`, `pyedflib`, `edfio`, `pymatreader`. This decision will
be revisited once the official Zenodo file listing and/or official DEJA-VU
source code is inspected (see `docs/dejavu_source_verification.md`).

## Outcome

**Audit dependency installation: INSTALLED** (10 of 10 identified missing
packages installed; 0 blocked; 0 skipped due to conflict).
