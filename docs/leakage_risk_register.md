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
| 9 | Manual synchronization uncertainty | Four modalities recorded at different sample rates (EEG 300 Hz, ECG 512 Hz, EMG 512 Hz, GSR ~10 Hz) require alignment to stimulus onset/offset; any manual or heuristic synchronization step is a source of label-timing error. **Sub-finding A — filename anomaly, RESOLVED by independent evidence:** `sub-P017/ses-S002/eeg/sub-P666_ses-S001_..._eeg.xdf` — full multi-source investigation in `docs/dejavu_identity_conflict_audit.md` (directory, database `session_metadata`/`journey`/`videos`, the official pipeline's own `clean_P017_S002.h5` output recording `subject_id=P017, session_id=S002` and the literal source path, a matching downstream segment file, no sibling file, no "666" anywhere in the database) all agree this is genuinely `P017`/`S002`; classified `PACKAGING_FILENAME_ONLY`. File left unmodified. **Sub-finding B — channel-order discrepancy, OPEN, dataset-wide:** the official code's assumed raw-channel order for the ECG (`Shimmer_BE1D`) and GSR (`Shimmer_894F`) Shimmer streams does not match the actual observed channel order (verified identically in two different files) — the code takes channel indices 0–3 for "ECG leads" and index 0 for "GSR conductance," but the true ECG lead channels are at indices 5–8 and true GSR conductance is at index 4 (indices 0–2/0-3 are accelerometer/status channels in both streams). This means the officially-distributed `preprocessed/*.h5` ECG and GSR data may not contain what its channel labels claim. Not fixed, not re-derived here — must be resolved before any modality-specific preprocessing or feature extraction. | Sub-finding A RESOLVED; sub-finding B OPEN |
| 10 | Post-performance fold modification | Changing fold composition, exclusion criteria, or preprocessing after seeing validation/test performance (non-negotiable rule #3: no performance-based fold selection). | OPEN — process control, not a data property; must be enforced procedurally throughout the project, not just recorded once |

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
