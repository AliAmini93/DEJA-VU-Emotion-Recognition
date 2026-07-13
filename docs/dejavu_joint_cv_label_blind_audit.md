# DEJA-VU Label-Blind Joint Subject-Stimulus CV Audit

Generated: `2026-07-13T16:15:51.482446+00:00`

No EEG/EMG model was trained. Fold construction used only participant identity, exact `VIDEO_NAME`, deterministic hashing, and balanced fold capacities. Labels were used only after each partition was fixed to audit feasibility.

## Cohort

| Metric | Value |
|---|---:|
| Participants | 24 |
| Participant-sessions | 30 |
| Emotional presentations | 90 |
| Exact videos | 16 |
| Manifest SHA-256 | `77f0b77c4c889cd62761bcd0f805a00de33d7803e112ade7055efe0fe8607a70` |

## Label-policy capacity

| Task | Policy | Retained | Discarded | Low | High | Majority accuracy |
|---|---|---:|---:|---:|---:|---:|
| valence | discard_midpoint | 75 | 15 | 53 | 22 | 0.7067 |
| valence | midpoint_as_low | 90 | 0 | 68 | 22 | 0.7556 |
| valence | midpoint_as_high | 90 | 0 | 53 | 37 | 0.5889 |
| arousal | discard_midpoint | 71 | 19 | 33 | 38 | 0.5352 |
| arousal | midpoint_as_low | 90 | 0 | 52 | 38 | 0.5778 |
| arousal | midpoint_as_high | 90 | 0 | 33 | 57 | 0.6333 |

Primary policy preference is `discard_midpoint` for both valence and arousal. It is accepted only if each task retains at least 70% of Cohort B.

Retention gate passed: `True`.

## Label-blind scheme robustness

| Scheme | Cells | Minimal pass rate | Strong pass rate | P05 min raw test | P05 V both-class fraction | P05 A both-class fraction | Robust candidate |
|---|---:|---:|---:|---:|---:|---:|---|
| 2x2 | 4 | 0.9290 | 0.0230 | 13.00 | 0.750 | 1.000 | True |
| 3x3 | 9 | 0.9770 | 0.5280 | 2.00 | 0.667 | 0.778 | True |
| 3x4 | 12 | 0.8620 | 0.3500 | 1.00 | 0.500 | 0.750 | False |
| 4x3 | 12 | 0.9150 | 0.4380 | 1.00 | 0.583 | 0.750 | False |
| 4x4 | 16 | 0.5690 | 0.0290 | 0.00 | 0.438 | 0.625 | False |

## Selected candidate scheme

- Selection status: **ROBUST_SCHEME_SELECTED**
- Scheme: **3x3**
- Outer cells per repetition: `9`
- Scheme selection used robustness distributions from label-blind partitions, not neural-model performance.

## Hash-derived repeated protocol

| Repetition | Role | Minimal | Strong | Min raw test | Valence both-class cells | Arousal both-class cells |
|---:|---|---|---|---:|---:|---:|
| 0 | primary | True | False | 4 | 7/9 | 9/9 |
| 1 | sensitivity | True | True | 7 | 9/9 | 9/9 |
| 2 | sensitivity | True | True | 4 | 8/9 | 7/9 |
| 3 | sensitivity | False | False | 1 | 8/9 | 8/9 |
| 4 | sensitivity | True | True | 5 | 8/9 | 9/9 |

No repetition was rerolled, removed, or replaced.

## Decision

**DO_NOT_LOCK_PROTOCOL**

Interpretation:

- `LOCK_LABEL_BLIND_REPEATED_PROTOCOL`: primary repetition passes the strong gate and every sensitivity repetition passes the minimal gate.
- `LOCK_WITH_CAPACITY_CAUTION`: primary and all sensitivity repetitions pass only the minimal gate.
- `DO_NOT_LOCK_PROTOCOL`: the selected scheme or repeated partitions do not meet the preregistered capacity requirements.

## Important metric rule

Because DEJA-VU is a sparse participant-video graph, some test cells may contain only one class even when the pooled repetition contains both classes. Future headline metrics must therefore be pooled over the complete repetition with participant/video-aware uncertainty. Cell-level Balanced Accuracy or ROC-AUC must not be reported for one-class cells.

## Outputs

- `docs/dejavu_joint_cv_label_blind_scheme_trials.csv`
- `docs/dejavu_joint_cv_label_blind_scheme_summary.csv`
- `docs/dejavu_joint_cv_label_blind_audit.md`
- `docs/dejavu_joint_cv_label_blind_audit.json`
- `docs/dejavu_joint_cv_label_blind_repeated_support.csv`
- `folds/dejavu_joint_cv_label_blind_repeated_protocol_candidate.json`
- `folds/dejavu_joint_cv_label_blind_repeated_assignments_candidate.csv`
- `folds/dejavu_joint_cv_primary_subject_folds_candidate.csv`
- `folds/dejavu_joint_cv_primary_video_folds_candidate.csv`

## Next stage

Only after this report is reviewed and the decision is accepted should the candidate files be renamed/frozen, committed, and used for shortcut/null audits. No model training is authorized by this script.
