# DEJA-VU Frozen Joint-CV Shortcut and Null Audit

Generated: `2026-07-14T08:54:22.956859+00:00`

No EEG, EMG, fusion, or physiological model was trained.

## Frozen evaluation scope

- Cohort B: 24 participants, 30 participant-sessions, 90 emotional presentations, 16 exact videos.
- Frozen 3×3 Joint Subject-Stimulus CV.
- Repetition 0 is primary; repetitions 1–4 are sensitivity.
- Primary labels use post-stimulus discard-midpoint policy.
- Predictions are pooled across all nine joint cells before headline metrics are calculated.

## Video/order structure

- Complete retained emotional sequences: `30`
- Unique three-video sequences: `28`
- Largest identical-sequence group: `2`
- NMI(video, emotional presentation position): `0.1103`
- Median unique positions per video: `3.00`
- Median modal-position fraction per video: `0.5227`

Unlike a perfect one-sequence dataset, position is not assumed to equal video identity. The measured association above determines how serious the legal position shortcut is.

## Primary repetition: legal joint-test baselines

| Task | Policy | Baseline | N | Accuracy | Balanced accuracy | Macro-F1 | ROC-AUC | Brier |
|---|---|---|---:|---:|---:|---:|---:|---:|
| arousal | discard_midpoint | global_train_prior | 71 | 0.3099 | 0.3074 | 0.3077 | 0.2273 | 0.3364 |
| arousal | discard_midpoint | position_quadratic_logistic | 71 | 0.3099 | 0.3194 | 0.3010 | 0.2723 | 0.3733 |
| arousal | discard_midpoint | position_train_prior | 71 | 0.2958 | 0.3002 | 0.2945 | 0.2763 | 0.3732 |
| valence | discard_midpoint | global_train_prior | 75 | 0.7067 | 0.5000 | 0.4141 | 0.3769 | 0.2202 |
| valence | discard_midpoint | position_quadratic_logistic | 75 | 0.6000 | 0.4378 | 0.4041 | 0.4713 | 0.2502 |
| valence | discard_midpoint | position_train_prior | 75 | 0.6000 | 0.4378 | 0.4041 | 0.4708 | 0.2502 |

## Primary shortcut gates for future physiological models

| Task | Best empirical legal baseline | Empirical BA | Mandatory BA gate | Gate source | Macro-F1 | ROC-AUC |
|---|---|---:|---:|---|---:|---:|
| valence | global_train_prior | 0.5000 | 0.5000 | empirical_legal_baseline | 0.4141 | 0.3769 |
| arousal | position_quadratic_logistic | 0.3194 | 0.5000 | theoretical_balanced_accuracy_chance | 0.3010 | 0.2723 |

A future EEG, EMG, or fusion model must be compared against the corresponding empirical legal shortcut and must also exceed theoretical 0.5 Balanced Accuracy. The mandatory BA gate is `max(0.5, best empirical legal-baseline BA)`.

## Primary repetition: diagnostic identity priors

| Task | Region | Baseline | Cell-evaluation N | Balanced accuracy | Macro-F1 | ROC-AUC |
|---|---|---|---:|---:|---:|---:|
| arousal | seen_subject_unseen_video | subject_train_prior | 142 | 0.6597 | 0.6354 | 0.7236 |
| arousal | unseen_subject_seen_video | video_train_prior | 142 | 0.5033 | 0.4214 | 0.5449 |
| valence | seen_subject_unseen_video | subject_train_prior | 150 | 0.5589 | 0.4771 | 0.5151 |
| valence | unseen_subject_seen_video | video_train_prior | 150 | 0.8150 | 0.8257 | 0.9064 |

These identity priors are diagnostic only. Their regions overlap across Cartesian cells, so scores are macro averages of defined cell metrics rather than a falsely independent pooled set. Subject identity and video identity are both unseen in the primary joint test.

## Position-shortcut null tests

Training labels, including the missing midpoint state, were permuted within each participant-session. Test labels were never permuted. FDR correction covers all repetition × task × shortcut tests.

| Rep | Role | Task | Baseline | Observed BA | Null median | Effect | p | FDR q | Significant |
|---:|---|---|---|---:|---:|---:|---:|---:|---|
| 0 | primary | valence | position_train_prior | 0.4378 | 0.5000 | -0.0622 | 0.912351 | 1.000000 | False |
| 0 | primary | valence | position_quadratic_logistic | 0.4378 | 0.5000 | -0.0622 | 0.952191 | 1.000000 | False |
| 0 | primary | arousal | position_train_prior | 0.3002 | 0.3369 | -0.0367 | 0.796813 | 1.000000 | False |
| 0 | primary | arousal | position_quadratic_logistic | 0.3194 | 0.3317 | -0.0124 | 0.601594 | 1.000000 | False |
| 1 | sensitivity | valence | position_train_prior | 0.4833 | 0.5039 | -0.0206 | 0.701195 | 1.000000 | False |
| 1 | sensitivity | valence | position_quadratic_logistic | 0.4833 | 0.5039 | -0.0206 | 0.796813 | 1.000000 | False |
| 1 | sensitivity | arousal | position_train_prior | 0.5674 | 0.5148 | 0.0526 | 0.059761 | 0.597610 | False |
| 1 | sensitivity | arousal | position_quadratic_logistic | 0.5734 | 0.5046 | 0.0688 | 0.031873 | 0.597610 | False |
| 2 | sensitivity | valence | position_train_prior | 0.4417 | 0.4944 | -0.0527 | 0.912351 | 1.000000 | False |
| 2 | sensitivity | valence | position_quadratic_logistic | 0.4378 | 0.4944 | -0.0566 | 0.968127 | 1.000000 | False |
| 2 | sensitivity | arousal | position_train_prior | 0.3074 | 0.4057 | -0.0983 | 1.000000 | 1.000000 | False |
| 2 | sensitivity | arousal | position_quadratic_logistic | 0.3074 | 0.3933 | -0.0859 | 0.972112 | 1.000000 | False |
| 3 | sensitivity | valence | position_train_prior | 0.5039 | 0.5000 | 0.0039 | 0.450199 | 1.000000 | False |
| 3 | sensitivity | valence | position_quadratic_logistic | 0.5000 | 0.5000 | 0.0000 | 0.633466 | 1.000000 | False |
| 3 | sensitivity | arousal | position_train_prior | 0.4601 | 0.4611 | -0.0010 | 0.505976 | 1.000000 | False |
| 3 | sensitivity | arousal | position_quadratic_logistic | 0.4601 | 0.4647 | -0.0046 | 0.561753 | 1.000000 | False |
| 4 | sensitivity | valence | position_train_prior | 0.4605 | 0.4927 | -0.0322 | 0.860558 | 1.000000 | False |
| 4 | sensitivity | valence | position_quadratic_logistic | 0.5000 | 0.4944 | 0.0056 | 0.438247 | 1.000000 | False |
| 4 | sensitivity | arousal | position_train_prior | 0.4904 | 0.4765 | 0.0140 | 0.378486 | 1.000000 | False |
| 4 | sensitivity | arousal | position_quadratic_logistic | 0.4964 | 0.4844 | 0.0120 | 0.358566 | 1.000000 | False |

## Decision

**PROCEED_WITH_STANDARD_SHORTCUT_GATE**

Mandatory rules:

1. Do not provide participant identity, exact video identity, canonical quadrant, emotion name, or held-out transition identity as physiological-model inputs.
2. Report improvement over the best legal primary-test shortcut.
3. Keep repetitions 1–4 for sensitivity only; do not tune on them.
4. Use dependence-aware uncertainty over participants/videos and paired comparisons against the shortcut baseline.
5. Preserve one-presentation and one-class cells in the pooled repetition; never score them as standalone headline metric units.

## Outputs

- `docs/dejavu_shortcut_baseline_cell_metrics.csv`
- `docs/dejavu_shortcut_baseline_summary.csv`
- `docs/dejavu_shortcut_null_tests.csv`
- `docs/dejavu_order_video_concentration.csv`
- `docs/dejavu_position_label_prevalence.csv`
- `docs/dejavu_shortcut_and_null_audit.json`
- `docs/dejavu_shortcut_and_null_audit.md`
