# Leakage Risk Register

This register tracks data-leakage and methodological risks specific to the
DEJA-VU dataset (multimodal EEG/ECG/EMG/GSR recordings of 28 participants
experiencing designed emotional transitions in VR, per
`docs/dejavu_source_verification.md`). It is initialized during the **Data-Only
Audit** phase, before any modeling work.

**No risk below may be marked "resolved" before the raw-data audit is
complete** (i.e., before the official archive is extracted, its internal
structure enumerated, and its labeling/segmentation scheme is directly
inspected — not inferred from the paper abstract).

| # | Risk | Description | Status |
|---|---|---|---|
| 1 | Participant/session leakage | Same participant's data appearing in both train and evaluation splits (must use subject-level, not segment-level or trial-level, splitting — e.g. strict LOSO as used for DEAP/I-DARE). | OPEN — raw data not yet inspected |
| 2 | Stimulus identity leakage | A model learning to recognize *which video stimulus* was shown rather than the *emotional state* it induced, especially since DEJA-VU uses a fixed, small set of validated stimuli across all participants. | OPEN |
| 3 | Segment-as-independent-sample error | Treating the dataset's "238 video-aligned physiological segments" (per Zenodo description) as 238 i.i.d. statistical samples, when they are non-independent sub-units of a smaller number of participants/trials. Segment count must never be used as statistical sample size (non-negotiable rule #5). | OPEN |
| 4 | Target-session preprocessing leakage | Any preprocessing (filtering, artifact rejection, normalization) that uses information from a session/segment that will later be held out for evaluation. | OPEN |
| 5 | Normalization using test data | Computing normalization statistics (mean/std, scalers) across the full dataset instead of fit-on-train-only, per fold. | OPEN |
| 6 | Sequence/order shortcut | The protocol's "balanced incomplete block design across six possible emotional sequences" and the fixed 69-second neutral reset periods could let a model key off presentation order or elapsed-time position rather than physiological content. | OPEN |
| 7 | Transition-label confounding | Because this dataset is specifically about *emotional transitions*, transition-adjacent segments may carry residual signal from the preceding emotional state, confounding the label of the current segment. | OPEN |
| 8 | Stimulus-label confounding | Emotional quadrant labels are tied to specific stimuli; if stimuli are not balanced/rotated per participant, quadrant/valence-arousal labels may be confounded with low-level stimulus properties (e.g. video brightness/audio loudness) rather than genuine affective response. | OPEN |
| 9 | Manual synchronization uncertainty / filename identity anomaly | Four modalities recorded at different sample rates (EEG 300 Hz, ECG 512 Hz, EMG 512 Hz, GSR ~10 Hz) require alignment to stimulus onset/offset; any manual or heuristic synchronization step is a source of label-timing error. **Filename anomaly — RESOLVED by independent evidence:** `sub-P017/ses-S002/eeg/sub-P666_ses-S001_..._eeg.xdf` — full multi-source investigation in `docs/dejavu_identity_conflict_audit.md` (directory, database `session_metadata`/`journey`/`videos`, the official pipeline's own `clean_P017_S002.h5` output recording `subject_id=P017, session_id=S002` and the literal source path, a matching downstream segment file, no sibling file, no "666" anywhere in the database) all agree this is genuinely `P017`/`S002`; classified `PACKAGING_FILENAME_ONLY`. File left unmodified. | RESOLVED (filename anomaly); general synchronization-fallback edge case still OPEN (see `docs/dejavu_trial_unit_preliminary_audit.md`, last-video-of-session `end_time` fallback) |
| 10 | Post-performance fold modification | Changing fold composition, exclusion criteria, or preprocessing after seeing validation/test performance (non-negotiable rule #3: no performance-based fold selection). | OPEN — process control, not a data property; must be enforced procedurally throughout the project, not just recorded once |
| 11 | **Physiological channel identity error (ECG/EMG/GSR)** — high severity | The official preprocessing code (`lib_preprocessing_utils.py::read_and_process_xdf`) selects ECG/EMG/GSR channels by **hardcoded positional index**, never consulting the channel descriptor (unlike EEG, which is descriptor-driven and correct). Verified across **all 34 sessions** with real signal statistics (`docs/dejavu_raw_channel_mapping_audit.md`): the code-selected "ECG" channels are 3 accelerometer axes + a channel that is **constant at 128.0 (zero variance) in every sample checked**; the code-selected "EMG" channels are `Battery` voltage + the same constant status channel; the code-selected "GSR" channel is a single accelerometer axis. The true ECG/EMG/GSR signal channels exist in the raw XDF at different indices and show the expected rich, continuously-varying, session-specific statistics. **EMG is one of this project's two stated primary modalities (with EEG) — this is the single highest-severity finding of the audit to date.** Not fixed, not re-derived here; a downstream decision (re-extract EMG/ECG/GSR directly from raw XDF at the correct indices, bypassing the distributed `preprocessed/segments` files for these three modalities) is required before any EMG/ECG/GSR feature work. | **OPEN — high severity, fully characterized, not fixed** |

## Process rule

Per the project's non-negotiable rules (`README.md`), during this phase:

- No SSI, PM-SSI-DG, LRSC-TTA, Transformer, Mamba, MoE, fusion, or
  hyperparameter search work is performed.
- No performance-based fold selection is performed.
- No segment is treated as an independent trial.
- No segment count is treated as a statistical sample size.

This register will be revisited once `DEJA-VU.rar` is extracted and its
internal file layout (participant/session/segment structure, label files,
synchronization metadata) is directly inspected.
