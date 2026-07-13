# DEJA-VU Local Environment Audit

Audit date (local): 2026-07-13 15:01 EEST (Europe/Vilnius, UTC+3) — NTP-synchronized
Audit type: read-only / non-destructive. No packages installed, no data downloaded, no environments created or modified.

---

## 1. Executive Decision

- **Recommendation: Option 3 — Create a new, dedicated Python virtual environment for DEJA-VU-Emotion-Recognition.** Do not reuse the DEAP/I-DARE `.venv` in place, and do not reuse the unrelated `HCI Tagging Database` venvs.
- The machine is a real, bare-metal Ubuntu 24.04.4 desktop (not a VM/container/WSL), with an NVIDIA RTX 5090 GPU, ample RAM/disk, working GitHub SSH+HTTPS auth, and a reachable GitHub API. Zenodo is temporarily in **scheduled maintenance** (HTTP 503) at the time of this audit — not a local configuration problem.
- The code repository `DEJA-VU-Emotion-Recognition` does **not** yet exist locally under `/mnt/HDD/AliWorks/`. The data directory `/mnt/HDD/AliWorks/DEJA-VU` exists, is empty, and is writable.
- No dataset was downloaded, no packages were installed, and no environment was created as part of this audit, per constraints.

---

## 2. Actual Execution Context

| Item | Value |
|---|---|
| Hostname | `Armin` |
| Current user | `armin` (uid=1000, groups: armin, adm, cdrom, sudo, dip, plugdev, users, lpadmin) |
| Working directory (audit session) | `/mnt/HDD/AliWorks` |
| OS | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Kernel | Linux 6.17.0-29-generic, SMP PREEMPT_DYNAMIC, x86_64 |
| CPU architecture | x86_64, Intel(R) Core(TM) Ultra 5 225F, 10 cores/threads |
| Hardware | ASRock Z890 Pro-A WiFi (desktop motherboard), firmware 1.39 |
| Shell | `/bin/bash` |
| Current date/time | Mon 2026-07-13 15:01:42 EEST |
| Timezone | Europe/Vilnius (EEST, UTC+3), NTP-synchronized (`System clock synchronized: yes`) |

**Environment classification: bare-metal Ubuntu desktop.** Evidence:
- `systemd-detect-virt` → `none` (exit code 1, which is the expected/normal result for *no* virtualization detected).
- No `/.dockerenv`; `/proc/1/cgroup` shows plain `0::/init.scope` (not a container cgroup layout).
- `/proc/version` shows a standard Ubuntu buildd kernel string, no `Microsoft`/WSL markers; no WSL-related environment variables.
- `SSH_CONNECTION`, `SSH_CLIENT`, `SSH_TTY` are all unset — this is a local session, not an SSH remote session. `who`/`w` show a local `seat0` graphical login.
- `hostnamectl` reports real desktop hardware (ASRock Z890 motherboard) and `nvidia-smi` shows a physical RTX 5090 with an active display (`Disp.A: On`), consistent with a physical desktop, not a cloud VM.

---

## 3. Disk and Mount Audit

| Filesystem | Type | Size | Used | Avail | Use% | Mounted on |
|---|---|---|---|---|---|---|
| `/dev/nvme0n1p2` | ext4 | 915G | 393G | 476G | 46% | `/` |
| `/dev/nvme0n1p1` | vfat | 1.1G | 6.2M | 1.1G | 1% | `/boot/efi` |
| `/dev/sda1` | ext4 | 1.8T | 711G | 1.1T | 41% | `/media/armin/External` |
| tmpfs | tmpfs | 32G | 719M | 31G | 3% | `/dev/shm` |

Inode availability (root fs `/dev/nvme0n1p2`): 59M total inodes, 1.1M used, 58M free (2% used) — ample headroom.

**Important finding:** `/mnt/HDD` is **not a separate mounted disk** despite its name. `findmnt -T /mnt/HDD/AliWorks` resolves to the **root filesystem** (`/dev/nvme0n1p2`, ext4), and `lsblk` confirms `nvme0n1p2` is the sole partition mounted at `/`. There is no `HDD`-labeled block device. `/mnt/HDD/AliWorks/...` is simply a directory tree on the root NVMe SSD (930.5 GB physical disk). A genuinely separate disk exists at `/dev/sda1` → `/media/armin/External` (1.8 TB, unrelated to this project).

**Implication:** all capacity/quota planning for DEJA-VU data and environments should use the root filesystem's real headroom (**476 GB free**, 46% used), not any dedicated "HDD" allocation.

---

## 4. Project Path Audit

| Path | Exists | Readable | Writable | Owner:Group | Perms | Notes |
|---|---|---|---|---|---|---|
| `/mnt` | Yes | Yes | No | root:root | 0755 | System mount root |
| `/mnt/HDD` | Yes | Yes | Yes | armin:armin | 0755 | Plain directory on root fs |
| `/mnt/HDD/AliWorks` | Yes | Yes | Yes | armin:armin | 0775 | Contains 19 entries (see below) |
| `/mnt/HDD/AliWorks/DEJA-VU` | Yes | Yes | Yes | armin:armin | 0775 | **Empty**, freshly created (birth: 2026-07-13 14:44) |
| `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition` | **No** | — | — | — | — | Not yet cloned |

`/mnt/HDD/AliWorks` top-level contents (19 entries): `DEAP/`, `DEJA-VU/`, `EmotionRecognitionDEAP-I-DARE/` (main repo) plus 11 sibling directories `EmotionRecognitionDEAP-I-DARE-{control, data-augmentation, idare-prior-best-confirm, label-task-protocol, repr-redesign-confirmation, repr-redesign-smoke, root-cause-triage, strict-ntd-smoke, w1a, w1b, w1c, w1d}` (confirmed via `git worktree list` to be **git worktrees of the same repository**, not separate clones), `HCI Tagging Database/`, `I-DARE/`.

---

## 5. Python Environment Inventory

No conda/mamba/micromamba/pyenv/poetry/pipenv/uv installation was found anywhere searched (`command -v` for all returned "not found"; no `~/miniconda3`, `~/anaconda3`, `~/.conda`, `~/.pyenv`, `/opt/conda`, etc.; no conda/pyenv init blocks in `~/.bashrc` or `~/.profile`). Package/environment management on this machine is done via **stdlib `venv`** exclusively.

Detected environments:

| # | Name | Type | Python | Location | Status |
|---|---|---|---|---|---|
| 1 | System Python | system | 3.12.3 (`/usr/bin/python3`) | `/usr` | Present, almost no scientific packages |
| 2 | **DEAP/I-DARE venv** | venv | 3.12.3 | `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE/.venv` | Actively used, most complete match for DEJA-VU's lineage |
| 3 | HCI venv | venv | 3.11.15 | `/mnt/HDD/AliWorks/HCI Tagging Database/HCI` | Complete generic stack incl. `mne`, but unrelated project (video/HCI tagging) |
| 4 | internvideo2_env | venv | 3.10.14 (nominal) | `/mnt/HDD/AliWorks/HCI Tagging Database/internvideo2_env` | **Broken** — `pyvenv.cfg` points to a foreign host (`/home/students4090/.pyenv/...`); `bin/python` does not exist locally |
| 5 | PyCharmMiscProject venv | venv | 3.12.3 | `/home/armin/PyCharmMiscProject/.venv` | Empty scratch venv, no packages installed |

Other environment marker files found (not separate environments): `requirements.txt` in each DEAP/I-DARE worktree (identical content, git worktrees share the same repo files), `/home/armin/Desktop/requirements.txt`, `/home/armin/Downloads/requirements-kaggle.txt`, `/home/armin/.espressif/python_env/idf6.2_py3.12_env` (ESP-IDF embedded firmware toolchain, irrelevant to this project).

No `environment.yml`/`environment.yaml`, `Pipfile`, `poetry.lock`, or `.python-version` files were found in the searched locations.

---

## 6. DEAP/I-DARE Environment Evidence

Repository located at: `/mnt/HDD/AliWorks/EmotionRecognitionDEAP-I-DARE`

| Item | Value |
|---|---|
| Active branch | `roca-idare-killtest` |
| Remote (origin) | `git@github.com:AliAmini93/EmotionRecognitionDEAP-I-DARE.git` |
| Working tree | Clean, up to date with `origin/roca-idare-killtest` |
| Last commit | `78946cb Add ROCA master status and results report` |
| `.venv` present | Yes — `.venv/pyvenv.cfg`: `home=/usr/bin`, `executable=/usr/bin/python3.12`, `version=3.12.3`, created via `/usr/bin/python3 -m venv` |
| `requirements.txt` | `numpy, scipy, pandas, scikit-learn, matplotlib, tqdm, pyyaml, torch, h5py, mat73` (72 bytes, minimal pinning — no version pins) |
| `.vscode/settings.json` | Not present in repo or in `~/.vscode` |
| README setup instructions | README.md is a research proposal/status document (Persian + English), not a setup guide; no explicit "run this to install" instructions found; references DEAP + I-DARE datasets, cross-subject LOSO protocol, EEG+EMG fusion — directly the predecessor project to DEJA-VU |

**Which environment was actually used — evidence, not inference from naming:**
`~/.bash_history` contains the literal command `source .venv/bin/activate`, confirming interactive use of the project-local `.venv` (not system Python, not a conda env). This is corroborated by the `.venv`'s installed package set (see §7) closely matching `requirements.txt` plus PyTorch with CUDA support already resolved.

---

## 7. Package Compatibility

Import checks were run by invoking each interpreter's binary directly (no `activate`, no installs). "OK" = importable in that interpreter right now.

### System Python3 (`/usr/bin/python3`, 3.12.3) — INCOMPATIBLE
Only `requests` (2.31.0) is present. All 24 other relevant packages missing, including `torch`. Site-packages are root-owned (`/usr/lib/python3/...`); installing into it would require `sudo` and would affect the whole system — not appropriate as a project environment.

### DEAP/I-DARE `.venv` (3.12.3) — USABLE WITH MISSING PACKAGES
| Package | Status | Version |
|---|---|---|
| numpy | OK | 2.4.4 |
| pandas | OK | 3.0.2 |
| scipy | OK | 1.17.1 |
| scikit-learn | OK | 1.8.0 |
| h5py | OK | 3.16.0 |
| mat73 | OK | (unversioned) |
| tqdm | OK | 4.67.3 |
| joblib | OK | 1.5.3 |
| matplotlib | OK | 3.10.9 |
| torch | OK | 2.11.0+cu128, **CUDA available: True** |
| pyarrow, tables, mne, pyxdf, edfio, pyedflib, pymatreader, openpyxl, sqlalchemy, requests, httpx, pooch, seaborn, jupyter, ipykernel, pytest | **MISSING** (16 packages) | — |

### HCI venv (3.11.15) — USABLE WITH MISSING PACKAGES (unrelated project)
Most complete generic data-science stack found on the machine: numpy 1.26.4, pandas 2.2.2, scipy 1.16.0, scikit-learn 1.6.1, h5py 3.14.0, **mne 1.11.0**, tqdm, requests, httpx, pooch, joblib, matplotlib, seaborn, jupyter, ipykernel, torch 2.9.1+cu128 (CUDA available: True). Missing: `pyarrow, tables, pyxdf, edfio, pyedflib, mat73, pymatreader, openpyxl, sqlalchemy, pytest` (10 packages). Belongs to the unrelated "HCI Tagging Database" (video) project — reusing it would break isolation between unrelated projects.

### PyCharmMiscProject venv (3.12.3) — INCOMPATIBLE
Empty scratch environment; only the interpreter itself, no scientific packages.

### internvideo2_env — INCOMPATIBLE
Non-functional as found: `pyvenv.cfg` references a different machine (`/home/students4090/.pyenv/versions/3.10.14/bin`), and `bin/python` does not exist on this filesystem. Cannot be used without full recreation.

**Conclusion:** no existing environment has the XDF/EDF-specific I/O stack (`pyxdf`, `edfio`, `pyedflib`, `mne`, `pymatreader`) together with the DEAP/I-DARE-style scientific stack (`numpy/pandas/scipy/sklearn/torch+CUDA`) in one place. The DEAP/I-DARE venv is closest in lineage and already has CUDA-enabled PyTorch working; the HCI venv is closest in package completeness but belongs to an unrelated project.

---

## 8. GPU / CUDA Status

| Item | Value |
|---|---|
| GPU | NVIDIA GeForce RTX 5090 (32,607 MiB / ~32 GB VRAM; 877 MiB in use by desktop compositor at audit time) |
| Driver | 580.159.03 |
| Driver-reported max CUDA version | 13.0 |
| `nvcc` (CUDA toolkit) | **Not installed** (`nvcc: command not found`), no `/usr/local/cuda*` |
| PyTorch (DEAP/I-DARE venv) | 2.11.0+cu128, `torch.cuda.is_available() == True` |
| PyTorch (HCI venv) | 2.9.1+cu128, `torch.cuda.is_available() == True` |
| PyTorch (system Python) | Not installed |
| RAM | 62 GiB total, 7.6 GiB free, **45 GiB available** (buff/cache reclaimable), 16 GiB used |
| Swap | 8.0 GiB total (`/swap.img`), 0 B used |

No system-wide CUDA toolkit is installed, but this is not a blocker: both existing PyTorch installs bundle their own CUDA 12.8 runtime (`+cu128` wheels) and successfully detect the GPU. No GPU/CUDA action was taken (no installs), per constraints.

---

## 9. Git and GitHub Access

| Item | Value |
|---|---|
| `git --version` | 2.43.0 |
| `git config user.name` | Ali Amini |
| `git config user.email` | 96921261+AliAmini93@users.noreply.github.com |
| `ssh -T git@github.com` | **Success**: `Hi AliAmini93! You've successfully authenticated, but GitHub does not provide shell access.` (exit code 1 — expected/normal for this GitHub probe) |
| `gh --version` | 2.45.0 |
| `gh auth status` | Logged in as `AliAmini93` via keyring token; scopes: `gist, read:org, repo, workflow`; protocol: https |
| Target repo local existence | `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition` **does not exist** |
| Target repo remote existence | Confirmed via `api.github.com/repos/AliAmini93/DEJA-VU-Emotion-Recognition` → public, non-empty repo object returned |

**Git/GitHub authentication is fully verified** via both SSH (used by the DEAP/I-DARE repo's existing remote) and `gh` HTTPS token auth.

---

## 10. Internet and Zenodo Access

| Target | DNS | Result |
|---|---|---|
| `www.nature.com` | Resolved | HTTP 200 (article page reachable; URL includes a cookie-consent redirect param, normal for Nature) |
| `doi.org` → `zenodo.org` | Resolved | Redirects to `zenodo.org/doi/10.5281/zenodo.17773125`, then **HTTP 503** |
| `zenodo.org/records/17773125` | Resolved | **HTTP 503** |
| `zenodo.org/` (homepage) | Resolved | **HTTP 503** — response body confirms: *"We'll be back soon... 2026-07-13 12:00 UTC: Zenodo will be unavailable for a few minutes because of a scheduled upgrade of our server infrastructure."* This is a **Zenodo-side scheduled maintenance window**, not a local network/proxy/DNS problem. |
| `api.zenodo.org/records/17773125` | **NXDOMAIN** | This hostname does not exist. **Correction:** Zenodo's REST API is served under the main domain at `https://zenodo.org/api/records/{id}`, not a separate `api.zenodo.org` host. Once the maintenance window ends, use `https://zenodo.org/api/records/17773125`. |
| `github.com/AliAmini93/DEJA-VU-Emotion-Recognition` | Resolved | HTTP 200 |
| `api.github.com/repos/...` | Resolved | HTTP 200, valid repo JSON returned |

No HTTP/HTTPS proxy environment variables are set (`env \| grep -i proxy` empty) — direct internet access, no proxy involved. No download of any dataset file was attempted; only HEAD requests and small JSON/HTML metadata responses were fetched.

---

## 11. Recommended Environment

**Decision: Option 3 — create a new, dedicated virtual environment for DEJA-VU-Emotion-Recognition.**

Rationale against the other options:
1. *Reuse DEAP/I-DARE venv unchanged* — rejected: it is missing 16 required packages (including `mne`, `pyxdf`, `edfio`, `pyedflib`, `pymatreader` — all central to reading EEG/EMG/XDF recordings).
2. *Reuse DEAP/I-DARE venv after installing missing packages* — rejected: that venv is **actively in use** on branch `roca-idare-killtest` with a clean working tree (live research work). Installing/upgrading packages into it (e.g., a newer `numpy`/`torch` for XDF/MNE compatibility) risks silently breaking DEAP/I-DARE reproducibility. The HCI venv is likewise excluded for the same isolation reason — it belongs to an unrelated (video/HCI) project.
3. **Reuse is rejected in favor of a new environment** because: (a) DEJA-VU is a distinct dataset/paper from DEAP/I-DARE, (b) isolation prevents cross-project dependency drift, (c) 476 GB of free disk space on the root filesystem makes a new ~2–5 GB venv trivial, (d) the existing `.venv`-per-project convention is already established for this user's other projects (`EmotionRecognitionDEAP-I-DARE/.venv`, `HCI Tagging Database/HCI`), so a new venv is consistent with local practice, and (e) `python3.12-venv` is already installed system-wide, so creation requires no package installation.
4. *Blocked / insufficient evidence* — not applicable; evidence is sufficient to decide.

**Proposed Python version:** 3.12.3 (matches system Python and the DEAP/I-DARE venv; the DEAP/I-DARE `requirements.txt`/package versions installed there prove 3.12 is compatible with `numpy 2.4`, `pandas 3.0`, `torch 2.11+cu128`, etc., on this machine).

---

## 12. Exact Activation Command

Environment does not exist yet. Once created (see §15), activate with:

```bash
source /mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition/.venv/bin/activate
```

---

## 13. Missing Dependencies

None of the packages below are installed anywhere they'd need to be for a fresh DEJA-VU venv (a fresh `venv` does not inherit system site-packages, matching `include-system-site-packages = false` used by the DEAP/I-DARE venv):

```
numpy pandas scipy scikit-learn pyarrow h5py tables mne pyxdf edfio pyedflib
mat73 pymatreader openpyxl sqlalchemy tqdm requests httpx pooch joblib
matplotlib seaborn jupyter ipykernel pytest
torch  (with CUDA 12.8 build, e.g. torch==2.11.0+cu128, matching the driver/GPU already validated on this machine)
```

**None of these were installed during this audit.**

---

## 14. Blocking Issues

1. Zenodo (`zenodo.org`, and by extension `doi.org/10.5281/zenodo.17773125`) is currently returning HTTP 503 due to a **scheduled maintenance window** announced as starting 2026-07-13 12:00 UTC ("a few minutes"). Dataset metadata/download cannot proceed until this clears. Re-check `https://zenodo.org/api/records/17773125` after retrying.
2. The code repository is not yet cloned to `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition`.
3. No dedicated Python environment exists yet for DEJA-VU; the closest existing environment (DEAP/I-DARE `.venv`) is missing 16 of the 25 audited packages, most critically the EEG/XDF I/O stack (`mne`, `pyxdf`, `edfio`, `pyedflib`, `pymatreader`).

None of these are infrastructure failures — they are expected pending-work items given the constraints of this audit (no cloning, no env creation, no downloads performed).

---

## 15. Exact Next Commands

Run in this order, **outside the scope of this audit** (each is a state-changing action requiring separate approval):

```bash
# 1. Clone the DEJA-VU-Emotion-Recognition repository (SSH auth already verified working)
git clone git@github.com:AliAmini93/DEJA-VU-Emotion-Recognition.git /mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition

# 2. Create a dedicated virtual environment (Python 3.12, matches system Python)
python3 -m venv /mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition/.venv

# 3. Activate it
source /mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition/.venv/bin/activate

# 4. Upgrade packaging tools, then install the required scientific/EEG stack (not run in this audit)
python -m pip install --upgrade pip
pip install numpy pandas scipy scikit-learn pyarrow h5py tables mne pyxdf edfio pyedflib \
  mat73 pymatreader openpyxl sqlalchemy tqdm requests httpx pooch joblib \
  matplotlib seaborn jupyter ipykernel pytest
pip install torch --index-url https://download.pytorch.org/whl/cu128

# 5. Once Zenodo maintenance clears, verify metadata access before any download
curl -sS https://zenodo.org/api/records/17773125
```

---

## Appendix: package availability matrix (raw)

See accompanying `python_environment_inventory.csv` for the full per-environment package matrix and `environment_audit_local.json` for the structured machine-readable equivalent of every section above.
