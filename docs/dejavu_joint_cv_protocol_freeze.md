# DEJA-VU Joint Subject-Stimulus CV Protocol Freeze

Frozen: `2026-07-13T16:19:26.792623+00:00`

## Decision

**LOCK_WITH_CAPACITY_CAUTION**

The 3×3 label-blind repeated protocol is frozen before any model training. Repetition 0 is primary; repetitions 1–4 are sensitivity analyses. No repetition was rerolled, removed, or replaced.

## Why the earlier automatic decision changed

The earlier gate returned `DO_NOT_LOCK_PROTOCOL` because one fixed sensitivity repetition contains a single raw observation in one Cartesian cell. That gate treated every cell as if it were a standalone metric unit. The intended estimand is instead the pooled prediction set over all nine Cartesian cells in a complete repetition.

This amendment was made before training and without observing model performance. The sparse repetition is preserved rather than rerolled.

## Frozen cohort and labels

| Item | Value |
|---|---:|
| Participants | 24 |
| Participant-sessions | 30 |
| Emotional presentations | 90 |
| Exact videos | 16 |
| Primary label policy | after-only discard midpoint |
| Valence retained low/high | 75; 53/22 |
| Arousal retained low/high | 71; 33/38 |

Score 5 remains in the manifest but has a missing label for the corresponding target. A multitask model must use task-specific loss masks.

## Frozen outer CV

- 3 subject folds × 3 video folds = 9 Cartesian cells.
- Every participant belongs to one subject fold per repetition.
- Every exact `VIDEO_NAME` belongs to one video fold per repetition.
- Train excludes all held-out participants and all held-out videos.
- Joint test is the intersection of held-out participants and held-out videos.
- Five SHA-256-derived repetitions are preserved exactly.

## Repetition capacity

| Repetition | Role | Raw test min/median/max | Valence both-class cells | Arousal both-class cells | Pooled valence | Pooled arousal |
|---:|---|---:|---:|---:|---:|---:|
| 0 | primary | 4/8.0/19 | 7/9 | 9/9 | 53/22 | 33/38 |
| 1 | sensitivity | 7/10.0/15 | 9/9 | 9/9 | 53/22 | 33/38 |
| 2 | sensitivity | 4/11.0/18 | 8/9 | 7/9 | 53/22 | 33/38 |
| 3 | sensitivity | 1/9.0/19 | 8/9 | 8/9 | 53/22 | 33/38 |
| 4 | sensitivity | 5/9.0/16 | 8/9 | 9/9 | 53/22 | 33/38 |

## Capacity cautions

- Sparse cells with fewer than two raw presentations: `1`.
- One-class task-specific cells across all repetitions: `8`.
- These cells remain in the protocol and contribute predictions to pooled repetition-level metrics.
- They must not be scored as standalone Balanced Accuracy, Macro-F1, or ROC-AUC units.

## Headline evaluation rule

For each target and repetition, concatenate predictions from all nine joint test cells and compute the metric once on the pooled repetition. Repetition 0 provides the primary result. Repetitions 1–4 provide sensitivity only and cannot be used for model selection.

## Acceptance checks

| Check | Result |
|---|---|
| `rep00_has_24_unique_participants` | PASS |
| `rep00_has_16_unique_videos` | PASS |
| `rep00_has_3_subject_folds` | PASS |
| `rep00_subject_folds_are_8_each` | PASS |
| `rep00_has_3_video_folds` | PASS |
| `rep00_video_fold_sizes_are_6_5_5` | PASS |
| `rep00_every_raw_row_has_exactly_one_cell` | PASS |
| `rep00_support_has_expected_rows` | PASS |
| `rep00_has_9_joint_cells` | PASS |
| `rep00_raw_cells_cover_90_rows_once` | PASS |
| `rep00_all_raw_cells_nonempty` | PASS |
| `rep00_valence_training_both_classes_all_cells` | PASS |
| `rep00_valence_pooled_retained_count` | PASS |
| `rep00_valence_pooled_low_count` | PASS |
| `rep00_valence_pooled_high_count` | PASS |
| `rep00_valence_pooled_has_both_classes` | PASS |
| `rep00_arousal_training_both_classes_all_cells` | PASS |
| `rep00_arousal_pooled_retained_count` | PASS |
| `rep00_arousal_pooled_low_count` | PASS |
| `rep00_arousal_pooled_high_count` | PASS |
| `rep00_arousal_pooled_has_both_classes` | PASS |
| `rep01_has_24_unique_participants` | PASS |
| `rep01_has_16_unique_videos` | PASS |
| `rep01_has_3_subject_folds` | PASS |
| `rep01_subject_folds_are_8_each` | PASS |
| `rep01_has_3_video_folds` | PASS |
| `rep01_video_fold_sizes_are_6_5_5` | PASS |
| `rep01_every_raw_row_has_exactly_one_cell` | PASS |
| `rep01_support_has_expected_rows` | PASS |
| `rep01_has_9_joint_cells` | PASS |
| `rep01_raw_cells_cover_90_rows_once` | PASS |
| `rep01_all_raw_cells_nonempty` | PASS |
| `rep01_valence_training_both_classes_all_cells` | PASS |
| `rep01_valence_pooled_retained_count` | PASS |
| `rep01_valence_pooled_low_count` | PASS |
| `rep01_valence_pooled_high_count` | PASS |
| `rep01_valence_pooled_has_both_classes` | PASS |
| `rep01_arousal_training_both_classes_all_cells` | PASS |
| `rep01_arousal_pooled_retained_count` | PASS |
| `rep01_arousal_pooled_low_count` | PASS |
| `rep01_arousal_pooled_high_count` | PASS |
| `rep01_arousal_pooled_has_both_classes` | PASS |
| `rep02_has_24_unique_participants` | PASS |
| `rep02_has_16_unique_videos` | PASS |
| `rep02_has_3_subject_folds` | PASS |
| `rep02_subject_folds_are_8_each` | PASS |
| `rep02_has_3_video_folds` | PASS |
| `rep02_video_fold_sizes_are_6_5_5` | PASS |
| `rep02_every_raw_row_has_exactly_one_cell` | PASS |
| `rep02_support_has_expected_rows` | PASS |
| `rep02_has_9_joint_cells` | PASS |
| `rep02_raw_cells_cover_90_rows_once` | PASS |
| `rep02_all_raw_cells_nonempty` | PASS |
| `rep02_valence_training_both_classes_all_cells` | PASS |
| `rep02_valence_pooled_retained_count` | PASS |
| `rep02_valence_pooled_low_count` | PASS |
| `rep02_valence_pooled_high_count` | PASS |
| `rep02_valence_pooled_has_both_classes` | PASS |
| `rep02_arousal_training_both_classes_all_cells` | PASS |
| `rep02_arousal_pooled_retained_count` | PASS |
| `rep02_arousal_pooled_low_count` | PASS |
| `rep02_arousal_pooled_high_count` | PASS |
| `rep02_arousal_pooled_has_both_classes` | PASS |
| `rep03_has_24_unique_participants` | PASS |
| `rep03_has_16_unique_videos` | PASS |
| `rep03_has_3_subject_folds` | PASS |
| `rep03_subject_folds_are_8_each` | PASS |
| `rep03_has_3_video_folds` | PASS |
| `rep03_video_fold_sizes_are_6_5_5` | PASS |
| `rep03_every_raw_row_has_exactly_one_cell` | PASS |
| `rep03_support_has_expected_rows` | PASS |
| `rep03_has_9_joint_cells` | PASS |
| `rep03_raw_cells_cover_90_rows_once` | PASS |
| `rep03_all_raw_cells_nonempty` | PASS |
| `rep03_valence_training_both_classes_all_cells` | PASS |
| `rep03_valence_pooled_retained_count` | PASS |
| `rep03_valence_pooled_low_count` | PASS |
| `rep03_valence_pooled_high_count` | PASS |
| `rep03_valence_pooled_has_both_classes` | PASS |
| `rep03_arousal_training_both_classes_all_cells` | PASS |
| `rep03_arousal_pooled_retained_count` | PASS |
| `rep03_arousal_pooled_low_count` | PASS |
| `rep03_arousal_pooled_high_count` | PASS |
| `rep03_arousal_pooled_has_both_classes` | PASS |
| `rep04_has_24_unique_participants` | PASS |
| `rep04_has_16_unique_videos` | PASS |
| `rep04_has_3_subject_folds` | PASS |
| `rep04_subject_folds_are_8_each` | PASS |
| `rep04_has_3_video_folds` | PASS |
| `rep04_video_fold_sizes_are_6_5_5` | PASS |
| `rep04_every_raw_row_has_exactly_one_cell` | PASS |
| `rep04_support_has_expected_rows` | PASS |
| `rep04_has_9_joint_cells` | PASS |
| `rep04_raw_cells_cover_90_rows_once` | PASS |
| `rep04_all_raw_cells_nonempty` | PASS |
| `rep04_valence_training_both_classes_all_cells` | PASS |
| `rep04_valence_pooled_retained_count` | PASS |
| `rep04_valence_pooled_low_count` | PASS |
| `rep04_valence_pooled_high_count` | PASS |
| `rep04_valence_pooled_has_both_classes` | PASS |
| `rep04_arousal_training_both_classes_all_cells` | PASS |
| `rep04_arousal_pooled_retained_count` | PASS |
| `rep04_arousal_pooled_low_count` | PASS |
| `rep04_arousal_pooled_high_count` | PASS |
| `rep04_arousal_pooled_has_both_classes` | PASS |
| `all_repetitions_subject_and_video_leakage_free` | PASS |
| `primary_repetition_passed_original_minimal_gate` | PASS |
| `all_five_hash_derived_repetitions_preserved` | PASS |
| `no_repetition_rerolled_or_removed` | PASS |
| `fold_construction_is_label_blind` | PASS |
| `source_manifest_hash_matches_frozen_hash` | PASS |

## Frozen outputs

- `folds/dejavu_joint_cv_protocol.json`
- `folds/dejavu_joint_cv_repeated_assignments.csv`
- `folds/dejavu_joint_cv_repeated_support.csv`
- `folds/dejavu_joint_cv_primary_subject_folds.csv`
- `folds/dejavu_joint_cv_primary_video_folds.csv`
- `manifests/dejavu_cohort_b_primary_labels.csv`
- `docs/dejavu_joint_cv_protocol_freeze.json`

## Next stage

Run repository tests and review this freeze report. After that, commit the completed data/QC/protocol artifacts before implementing raw-EMG extraction or model training.
