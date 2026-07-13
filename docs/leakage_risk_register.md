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
| 9 | Manual synchronization uncertainty | Four modalities recorded at different sample rates (EEG 300 Hz, ECG 512 Hz, EMG 512 Hz, GSR 10 Hz) require alignment to stimulus onset/offset; any manual or heuristic synchronization step is a source of label-timing error that must be documented once the raw data and code (`DEJA_VU_code.rar`) are inspected. **Observed evidence (from archive listing, not yet extracted content):** `docs/dejavu_acquisition_report.md` records that the file at path `DEJA-VU/raw/sub-P017/ses-S002/eeg/...` is *named* `sub-P666_ses-S001_...eeg.xdf` — a participant/session identity mismatch between path and filename in the official archive itself. `P666` matches none of the 28 enrolled participants. This must be resolved (very likely by confirming with the directory path, but that must be verified against `deja_vu_database.db` / `data.xlsx`, not assumed) before this file is used in any subject-level split. | OPEN |
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
