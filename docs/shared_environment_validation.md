# Shared Environment Validation

Executed: 2026-07-13T15:32:58+03:00 (Europe/Vilnius)

## `which python` check

```
$ source /mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/activate
$ which python
/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/python
```

**Result: MATCH.** The active interpreter is exactly
`/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/python`, as required by
`docs/shared_environment_policy.md`.

| Check | Value |
|---|---|
| `which python` | `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/python` |
| `which pip` | `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/pip` |
| `python --version` | Python 3.12.3 |
| No new `.venv` created under DEJA-VU-Emotion-Recognition | Confirmed — directory does not exist |
| HCI environments touched | No |
| DEAP/I-DARE repository files modified | No |

## Pre-install snapshot

```
mkdir -p /mnt/HDD/AliWorks/DEJA-VU
python -m pip freeze > /mnt/HDD/AliWorks/DEJA-VU/shared_environment_before_dejavu.txt
```

| Item | Value |
|---|---|
| Snapshot file | `/mnt/HDD/AliWorks/DEJA-VU/shared_environment_before_dejavu.txt` (also copied to `docs/shared_environment_before_dejavu.txt`) |
| Size | 1091 bytes |
| Packages captured | 52 |
| SHA-256 | `9ce1a9fa462cd6f610b2b9104aa1cf772f56b71a72f6586dd0e71e0df488a7b1` |

### Protected core package versions at snapshot time

| Package | Version |
|---|---|
| numpy | 2.4.4 |
| pandas | 3.0.2 |
| scipy | 1.17.1 |
| scikit-learn | 1.8.0 |
| h5py | 3.16.0 |
| matplotlib | 3.10.9 |
| torch | 2.11.0+cu128 |
| joblib | 1.5.3 |
| tqdm | 4.67.3 |
| mat73 | 0.65 |

These 10 versions are the baseline. Any subsequent installation step
(`docs/environment_import_validation.md`) must reproduce identical versions for
all ten, or the installation is treated as a policy violation and must be
documented as a conflict rather than silently applied.

## Outcome

Shared environment validation: **VERIFIED**. See `docs/environment_import_validation.md`
for the subsequent import-check and dependency-installation results, and confirm
there that all 10 protected core versions above are unchanged after installation.
