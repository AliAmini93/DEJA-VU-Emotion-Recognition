# DEJA-VU Raw Channel Mapping Forensic Audit

**Severity: high.** This audit finds that the officially-distributed
`preprocessed/*.h5` and `segments/**/*.h5` files' ECG, EMG, and GSR data
almost certainly do **not** contain the physiological signals their channel
labels claim — they appear to contain accelerometer axes, battery voltage,
and a constant status byte instead. EEG is unaffected and verified correct.
This is a **dataset-wide** finding (confirmed across all 34 sessions), not
specific to the P666-filename anomaly.

Produced by `scripts/01_audit_dejavu_channel_mapping.py` (read-only; loads
raw sample arrays only for 3 representative sessions to compute summary
statistics — no filtering, no ICA, no model preprocessing, no file
modification). Full per-channel-per-session detail (952 rows, 34 sessions ×
28 channels/session): `docs/dejavu_raw_channel_mapping_by_session.csv`.

## Method

1. **Code inspection, line-by-line** (`lib_preprocessing_utils.py::read_and_process_xdf`):
   confirmed **no reordering, sorting, or descriptor-based verification**
   occurs anywhere before index selection for the three Shimmer streams
   (`grep`-verified: zero matches for `sort|reorder|argsort|permut` in the
   file). EEG is the *only* modality whose selection is descriptor-driven
   (`channels = stream['info']['desc'][0]['channels'][0]['channel']`, then
   `keep_indices` computed by excluding the label `"TRG"`). ECG/EMG/GSR are
   each selected by a **hardcoded positional slice**
   (`time_series[:, :4]`, `[:, :2]`, `[:, 0]`) with **no read of the channel
   descriptor at all** for these three streams.
2. **Verified the assumption that visible XDF order equals array order**:
   confirmed directly — `pyxdf` returns `stream['time_series']` with columns
   in the exact order declared by the stream's channel descriptor (this is
   an LSL protocol guarantee, not assumed); cross-checked by reading the
   descriptor's `channel` list length and comparing to `time_series.shape[1]`
   for every stream in every session (they always match).
3. **All 34 sessions checked**, not a sample: for every channel of every
   stream in every raw XDF file, recorded whether the official code selects
   it, what label the code assigns to it, and whether that assigned label
   is a plausible match for the descriptor's *true* label at that index (see
   `TRUE_SIGNAL_MATCHERS` in the script — precise matching, e.g. explicitly
   excluding `ECG_EMG_Status1` from counting as a true ECG channel despite
   containing the substring `"ECG"`).
4. **Deep dive with real sample statistics** for 3 representative, well-
   separated sessions: `P001/S001`, `P017/S002` (the P666-filename session),
   `P010/S001`. For each, computed mean/std/min/max/range/unique-value-count
   for both the code-selected channels and the true signal channels.

## Findings by modality

### EEG — `EEG_MAPPING_VERIFIED`

Descriptor-driven selection (`keep_indices` excludes only `"TRG"`), so the 7
retained channels (`F3,S2-S7` → `FP1,FP2,C3,C4,LE,EOG1,EOG2`) are correct by
construction, for all 34 sessions. No discrepancy found.

### GSR (`Shimmer_894F`) — `GSR_MAPPING_INCORRECT`, all 34 sessions

Code takes column index 0, labels it `GSR_Conductance`. The true descriptor
order is `[Accel_LN_X, Accel_LN_Y, Accel_LN_Z, GSR_Skin_Resistance,
GSR_Skin_Conductance, GSR_Range, PPG_A13]` — index 0 is **`Accel_LN_X`**, an
accelerometer axis. Real statistics (3 sessions):

| Session | Code-selected (`Accel_LN_X`) | True (`GSR_Skin_Conductance`) |
|---|---|---|
| P001/S001 | mean −5.99, range 15.09, 20 unique/1000 | mean 0.70, range 0.89, 750 unique/1000 |
| P017/S002 | mean −0.57, range 14.83, 66 unique/1000 | mean 0.28, range 0.07, 4 unique/1000 |
| P010/S001 | mean −4.28, range 2.23, 15 unique/1000 | mean 0.32, range 0.03, 8 unique/1000 |

The code-selected channel's mean/range varies wildly and non-monotonically
across sessions in a pattern consistent with device orientation, not
physiology; its value range (roughly −9 to +9) is inconsistent with a skin
conductance signal (typically a small positive value, µS-scale, as seen in
the true channel: 0.03–1.4).

### EMG (`Shimmer_BBBD`) — `EMG_MAPPING_INCORRECT`, all 34 sessions

Code takes columns 0–1, labels them `EMG_Zygomaticus, EMG_Trapezius`. True
descriptor order is `[Battery, ECG_EMG_Status1, EMG_CH1_24BIT,
EMG_CH2_24BIT]` — indices 0–1 are **`Battery`** and **`ECG_EMG_Status1`**.
Real statistics (3 sessions):

| Session | `Battery` (code idx 0) | `ECG_EMG_Status1` (code idx 1) | True `EMG_CH1/CH2_24BIT` |
|---|---|---|---|
| P001/S001 | mean 3774.6, range 115.8 (mV-scale battery voltage) | **constant 128.0, std=0.0** | mean 7.7/9.6, range 13.9/10.6, 589–772 unique/1000 |
| P017/S002 | mean 3768.6, range 170.0 | **constant 128.0, std=0.0** | mean −6.5/−2.8, range 1.3/3.9, 808–841 unique/1000 |
| P010/S001 | mean 3753.3, range 170.0 | **constant 128.0, std=0.0** | mean 2.6/−1.0, range 1.5/1.7, 732–931 unique/1000 |

`ECG_EMG_Status1` is **exactly `128.0` in every single sample checked, across
all three sessions** (a fixed status/flag byte) — this is being distributed
as one of the two "EMG" channels (`EMG_Trapezius`) in every
`preprocessed/*.h5` file. `Battery` (the other "EMG" channel,
`EMG_Zygomaticus`) tracks battery voltage, not muscle activity. The true EMG
channels show the expected rich, session-varying, continuously-distributed
signal.

### ECG (`Shimmer_BE1D`) — `ECG_MAPPING_INCORRECT`, all 34 sessions

Code takes columns 0–3, labels them `ECG_Lead_I, ECG_Lead_II, ECG_Lead_III,
ECG_Chest`. True descriptor order is `[Accel_LN_X, Accel_LN_Y, Accel_LN_Z,
ECG_EMG_Status1, ECG_EMG_Status2, ECG_LL-RA_24BIT, ECG_LA-RA_24BIT,
ECG_LL-LA_24BIT, ECG_Vx-RL_24BIT]` — indices 0–3 are **three accelerometer
axes plus the same constant status byte**. Real statistics (3 sessions):

| Session | `Accel_LN_Z` (code idx 2) | `ECG_EMG_Status1` (code idx 3) | True `ECG_LL-RA_24BIT` (real lead) |
|---|---|---|---|
| P001/S001 | mean 5.12, range 6.99 | constant 128.0 | mean 1.30, range 4.27, 766 unique/1000 |
| P017/S002 | mean 10.74, range 10.62 | constant 128.0 | mean −1.88, range 3.24, 876 unique/1000 |
| P010/S001 | mean 10.42, range 1.37 | constant 128.0 | mean 4.67 (LL-LA), range 3.04, 903 unique/1000 |

The accelerometer-Z mean shifts from ~5 to ~10–11 across sessions in a way
consistent with a device being worn in different orientations at different
recording times — a physically implausible pattern for a re-referenced ECG
lead, but an entirely expected one for a body-worn accelerometer.

## Why this matters

- `preprocessed/*.h5` and `segments/**/*.h5` files' `ecg` and `emg` groups
  (as distributed) most likely contain accelerometer/battery/status data
  mislabeled as physiological signal, for **all 34 sessions**. `gsr` groups
  most likely contain a single accelerometer axis mislabeled as skin
  conductance.
- This is a defect in the **official distributed code**
  (`lib_preprocessing_utils.py`), not something introduced by this audit or
  by the extraction process. The raw XDF files themselves are correct and
  complete — the true ECG/EMG/GSR signal *is* present in the raw data, at
  different column indices than the official code reads.
- **EEG is unaffected.** The project's stated primary modalities are EEG and
  EMG (per the task instructions); EEG is verified correct, but EMG is
  verified **incorrect** — this is the most consequential single finding of
  this audit stage for the project's own stated priorities.
- **No file was modified, no correction was applied.** This audit only
  reports the discrepancy with supporting evidence; deciding whether/how to
  re-derive correct channels from the raw XDF (bypassing the official
  "clean" files for these three modalities) is a downstream decision, out of
  scope for this Data-Only Audit stage.

## Classification summary

| Modality | Classification |
|---|---|
| EEG | `EEG_MAPPING_VERIFIED` |
| EMG | `EMG_MAPPING_INCORRECT` |
| ECG | `ECG_MAPPING_INCORRECT` |
| GSR | `GSR_MAPPING_INCORRECT` |

Logged as an update to `docs/leakage_risk_register.md` risk #9, sub-finding
B (previously "OPEN, unresolved" based on a 2-file spot check; now
confirmed across all 34 sessions with real signal statistics — still
**OPEN**, in the sense that no fix has been applied, but now fully
characterized rather than merely suspected).
