# Shared Python Environment Policy

## Decision

DEAP, I-DARE, and DEJA-VU **share a single Python environment**. This overrides the
"create a new dedicated environment" recommendation made in the initial local
environment audit (`docs/environment_audit.md`, section 11). That recommendation
was superseded by an explicit user decision recorded here.

## Canonical environment path

```
/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv
```

Canonical Python executable:

```
/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/python
```

Activation command:

```bash
source /mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv/bin/activate
```

## Rules

1. **No DEJA-VU-specific virtual environment is created.** There is no
   `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition/.venv` and none should be created
   unless this policy is explicitly revised.
2. The HCI Tagging Database environments (`HCI Tagging Database/HCI`,
   `HCI Tagging Database/internvideo2_env`) are **not** used or modified by DEJA-VU
   work under any circumstance.
3. The DEAP/I-DARE repository and its git worktrees are never modified by DEJA-VU
   tooling. DEJA-VU only *reads* the shared interpreter; it does not write into
   `EmotionRecognitionDEAP-I-DARE/`.

## Trade-offs (explicit)

- **Benefit:** reduces duplicate disk usage — one copy of NumPy/PyTorch/SciPy/etc.
  instead of three, and avoids re-resolving a large CUDA-enabled PyTorch install.
- **Cost:** increases dependency coupling between DEAP/I-DARE and DEJA-VU. A
  package version required by one project's code can silently affect the other.
  There is no environment isolation between them going forward.

## Protected core packages

The following packages are load-bearing for the existing DEAP/I-DARE work and
must **not** be upgraded, downgraded, or replaced as a side effect of installing
DEJA-VU-only dependencies:

```
numpy
pandas
scipy
scikit-learn
h5py
matplotlib
torch
joblib
tqdm
mat73
```

## Required safety procedure before any install

1. Snapshot the environment with `pip freeze` **before** any change
   (`shared_environment_before_dejavu.txt` / `docs/shared_environment_before_dejavu.txt`).
2. Run `python -m pip install --dry-run <packages>` first and inspect the plan.
3. If the dry run proposes changing any protected core package, **stop** and
   document the conflict instead of installing.
4. If the dry run is safe, install only the missing packages.
5. Run `python -m pip check` after installation.
6. Re-verify `torch.__version__` and `torch.cuda.is_available()` are unchanged
   from before the install.
7. Record the resulting package set in `requirements-lock.txt` and record only
   the DEJA-VU-added packages in `requirements-dejavu-overlay.txt`.

See `docs/shared_environment_validation.md` and
`docs/shared_environment_validation.json` for the executed validation, and
`docs/environment_import_validation.md` / `.json` for the per-package import
results and installation outcome.
