#!/usr/bin/env python3
"""Integrated label-blind Joint Subject-Stimulus CV audit for DEJA-VU Cohort B.

This script performs, in one deterministic pre-training audit:

1. Re-checks the three binary label policies for post-stimulus valence/arousal.
2. Compares label-blind subject/video fold schemes:
      2x2, 3x3, 3x4, 4x3, 4x4
3. Evaluates 1000 deterministic label-blind random partitions per scheme.
4. Selects the largest scheme satisfying predeclared robustness gates.
5. Generates five hash-derived, label-blind repetitions:
      repetition 0 = primary
      repetitions 1-4 = sensitivity
6. Produces a candidate protocol decision without training any model.

Important:
- Fold construction never uses labels, EEG, EMG, predictions, or model metrics.
- Exact VIDEO_NAME is the content identity.
- All sessions of a participant remain in one subject fold.
- No unfavorable repetition is rerolled or replaced.
- Existing artifacts are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


SCHEMES: tuple[tuple[int, int], ...] = (
    (2, 2),
    (3, 3),
    (3, 4),
    (4, 3),
    (4, 4),
)
TASKS = ("valence", "arousal")
POLICIES = (
    "discard_midpoint",
    "midpoint_as_low",
    "midpoint_as_high",
)
PREFERRED_POLICY = "discard_midpoint"
DEFAULT_RANDOM_PARTITIONS = 1000
DEFAULT_REPETITIONS = 5

# Predeclared gates. These are not modified after seeing the results.
ROBUST_MINIMAL_PASS_RATE = 0.80
PRIMARY_POLICY_MIN_GLOBAL_RETENTION = 0.70
MINIMAL_BOTH_CLASS_CELL_FRACTION = 0.50
STRONG_BOTH_CLASS_CELL_FRACTION = 0.75
MINIMAL_MIN_RAW_TEST_ROWS = 2
STRONG_MIN_RAW_TEST_ROWS = 3
MINIMAL_MIN_RETAINED_TEST_ROWS = 1
STRONG_MIN_RETAINED_TEST_ROWS = 2
MINIMAL_MIN_TRAIN_CLASS = 1
STRONG_MIN_TRAIN_CLASS = 5


class AuditError(RuntimeError):
    pass


@dataclass
class PolicyMetrics:
    task: str
    policy: str
    retained_global: int
    discarded_global: int
    low_global: int
    high_global: int
    empty_test_cells: int
    one_class_test_cells: int
    both_class_test_cells: int
    both_class_cell_fraction: float
    min_retained_test_rows: int
    median_retained_test_rows: float
    max_retained_test_rows: int
    min_train_class_count: int
    train_one_class_cells: int


@dataclass
class PartitionEvaluation:
    subject_folds: int
    video_folds: int
    raw_empty_cells: int
    min_raw_test_rows: int
    median_raw_test_rows: float
    max_raw_test_rows: int
    policy_metrics: dict[tuple[str, str], PolicyMetrics]
    minimal_pass: bool
    strong_pass: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--random-partitions",
        type=int,
        default=DEFAULT_RANDOM_PARTITIONS,
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=DEFAULT_REPETITIONS,
    )
    return parser.parse_args()


def refuse_overwrite(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        formatted = "\n".join(f"- {path}" for path in existing)
        raise FileExistsError(
            "Refusing to overwrite existing audit outputs:\n" + formatted
        )


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def make_binary(scores: pd.Series, policy: str) -> np.ndarray:
    numeric = pd.to_numeric(scores, errors="coerce").to_numpy(dtype=float)
    labels = np.full(numeric.shape, -1, dtype=int)

    if policy == "discard_midpoint":
        labels[numeric < 5] = 0
        labels[numeric > 5] = 1
    elif policy == "midpoint_as_low":
        labels[numeric <= 5] = 0
        labels[numeric > 5] = 1
    elif policy == "midpoint_as_high":
        labels[numeric < 5] = 0
        labels[numeric >= 5] = 1
    else:
        raise ValueError(policy)

    labels[~np.isfinite(numeric)] = -1
    return labels


def balanced_capacities(n_entities: int, n_folds: int) -> np.ndarray:
    base = n_entities // n_folds
    remainder = n_entities % n_folds
    capacities = np.full(n_folds, base, dtype=int)
    capacities[:remainder] += 1
    return capacities


def assignment_from_seed(
    n_entities: int,
    n_folds: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    capacities = balanced_capacities(n_entities, n_folds)
    template = np.concatenate(
        [
            np.full(capacity, fold_id, dtype=int)
            for fold_id, capacity in enumerate(capacities)
        ]
    )
    if template.size != n_entities:
        raise AssertionError((template.size, n_entities))
    shuffled_entities = rng.permutation(n_entities)
    assignment = np.empty(n_entities, dtype=int)
    assignment[shuffled_entities] = template
    return assignment


def derived_seed(manifest_hash: str, *parts: object) -> int:
    payload = "|".join([manifest_hash, *[str(part) for part in parts]])
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**63 - 1)


def evaluate_partition(
    participant_fold: np.ndarray,
    video_fold: np.ndarray,
    row_participant_index: np.ndarray,
    row_video_index: np.ndarray,
    labels: dict[tuple[str, str], np.ndarray],
) -> PartitionEvaluation:
    subject_folds = int(participant_fold.max()) + 1
    video_folds = int(video_fold.max()) + 1
    n_cells = subject_folds * video_folds

    row_subject_fold = participant_fold[row_participant_index]
    row_video_fold = video_fold[row_video_index]
    raw_test_counts: list[int] = []
    cell_masks: list[tuple[np.ndarray, np.ndarray]] = []

    for subject_fold_id in range(subject_folds):
        subject_held = row_subject_fold == subject_fold_id
        for video_fold_id in range(video_folds):
            video_held = row_video_fold == video_fold_id
            test_mask = subject_held & video_held
            train_mask = (~subject_held) & (~video_held)
            raw_test_counts.append(int(test_mask.sum()))
            cell_masks.append((test_mask, train_mask))

    raw_array = np.asarray(raw_test_counts, dtype=int)
    policy_results: dict[tuple[str, str], PolicyMetrics] = {}

    for key, target in labels.items():
        task, policy = key
        retained_test_counts: list[int] = []
        empty_test_cells = 0
        one_class_test_cells = 0
        both_class_test_cells = 0
        min_train_class_count = 10**9
        train_one_class_cells = 0

        for test_mask, train_mask in cell_masks:
            test_labels = target[test_mask]
            test_labels = test_labels[test_labels >= 0]
            train_labels = target[train_mask]
            train_labels = train_labels[train_labels >= 0]

            retained_test_counts.append(int(test_labels.size))
            if test_labels.size == 0:
                empty_test_cells += 1
            elif np.unique(test_labels).size == 1:
                one_class_test_cells += 1
            else:
                both_class_test_cells += 1

            train_low = int((train_labels == 0).sum())
            train_high = int((train_labels == 1).sum())
            min_train_class_count = min(
                min_train_class_count,
                train_low,
                train_high,
            )
            if train_low == 0 or train_high == 0:
                train_one_class_cells += 1

        retained_array = np.asarray(retained_test_counts, dtype=int)
        retained_global = int((target >= 0).sum())
        low_global = int((target == 0).sum())
        high_global = int((target == 1).sum())

        policy_results[key] = PolicyMetrics(
            task=task,
            policy=policy,
            retained_global=retained_global,
            discarded_global=int(len(target) - retained_global),
            low_global=low_global,
            high_global=high_global,
            empty_test_cells=empty_test_cells,
            one_class_test_cells=one_class_test_cells,
            both_class_test_cells=both_class_test_cells,
            both_class_cell_fraction=both_class_test_cells / n_cells,
            min_retained_test_rows=int(retained_array.min()),
            median_retained_test_rows=float(np.median(retained_array)),
            max_retained_test_rows=int(retained_array.max()),
            min_train_class_count=int(min_train_class_count),
            train_one_class_cells=train_one_class_cells,
        )

    preferred_metrics = [
        policy_results[(task, PREFERRED_POLICY)]
        for task in TASKS
    ]

    minimal_pass = bool(
        int((raw_array == 0).sum()) == 0
        and int(raw_array.min()) >= MINIMAL_MIN_RAW_TEST_ROWS
        and all(
            metric.empty_test_cells == 0
            and metric.train_one_class_cells == 0
            and metric.min_train_class_count >= MINIMAL_MIN_TRAIN_CLASS
            and metric.min_retained_test_rows
            >= MINIMAL_MIN_RETAINED_TEST_ROWS
            and metric.both_class_cell_fraction
            >= MINIMAL_BOTH_CLASS_CELL_FRACTION
            for metric in preferred_metrics
        )
    )

    strong_pass = bool(
        int((raw_array == 0).sum()) == 0
        and int(raw_array.min()) >= STRONG_MIN_RAW_TEST_ROWS
        and all(
            metric.empty_test_cells == 0
            and metric.train_one_class_cells == 0
            and metric.min_train_class_count >= STRONG_MIN_TRAIN_CLASS
            and metric.min_retained_test_rows
            >= STRONG_MIN_RETAINED_TEST_ROWS
            and metric.both_class_cell_fraction
            >= STRONG_BOTH_CLASS_CELL_FRACTION
            for metric in preferred_metrics
        )
    )

    return PartitionEvaluation(
        subject_folds=subject_folds,
        video_folds=video_folds,
        raw_empty_cells=int((raw_array == 0).sum()),
        min_raw_test_rows=int(raw_array.min()),
        median_raw_test_rows=float(np.median(raw_array)),
        max_raw_test_rows=int(raw_array.max()),
        policy_metrics=policy_results,
        minimal_pass=minimal_pass,
        strong_pass=strong_pass,
    )


def percentile(values: list[float], q: float) -> float:
    return float(np.quantile(np.asarray(values, dtype=float), q))


def main() -> int:
    args = parse_args()
    if args.random_partitions < 100:
        raise AuditError("--random-partitions must be at least 100")
    if args.repetitions != 5:
        raise AuditError(
            "This protocol is preregistered for exactly five repetitions"
        )

    repo_root = args.repo_root.resolve()
    manifests_dir = repo_root / "manifests"
    docs_dir = repo_root / "docs"
    folds_dir = repo_root / "folds"
    docs_dir.mkdir(parents=True, exist_ok=True)
    folds_dir.mkdir(parents=True, exist_ok=True)

    source_path = (
        manifests_dir / "dejavu_cohort_b_emotional_label_candidates.csv"
    )
    if not source_path.exists():
        raise AuditError(f"Required source manifest missing: {source_path}")

    output_paths = [
        docs_dir / "dejavu_joint_cv_label_blind_scheme_trials.csv",
        docs_dir / "dejavu_joint_cv_label_blind_scheme_summary.csv",
        docs_dir / "dejavu_joint_cv_label_blind_audit.md",
        docs_dir / "dejavu_joint_cv_label_blind_audit.json",
        docs_dir / "dejavu_joint_cv_label_blind_repeated_support.csv",
        folds_dir / "dejavu_joint_cv_label_blind_repeated_protocol_candidate.json",
        folds_dir / "dejavu_joint_cv_label_blind_repeated_assignments_candidate.csv",
        folds_dir / "dejavu_joint_cv_primary_subject_folds_candidate.csv",
        folds_dir / "dejavu_joint_cv_primary_video_folds_candidate.csv",
    ]
    refuse_overwrite(output_paths)

    source_bytes = source_path.read_bytes()
    manifest_hash = hashlib.sha256(source_bytes).hexdigest()
    frame = pd.read_csv(source_path)

    required_columns = {
        "participant_id",
        "session_id",
        "participant_session_key",
        "presentation_id",
        "video_name",
        "after_valence",
        "after_arousal",
    }
    missing = sorted(required_columns - set(frame.columns))
    if missing:
        raise AuditError(f"Source manifest missing columns: {missing}")

    if len(frame) != 90:
        raise AuditError(f"Expected 90 emotional presentations, found {len(frame)}")
    if frame["participant_id"].nunique() != 24:
        raise AuditError(
            f"Expected 24 participants, found {frame['participant_id'].nunique()}"
        )
    if frame["participant_session_key"].nunique() != 30:
        raise AuditError(
            "Expected 30 participant-sessions, found "
            f"{frame['participant_session_key'].nunique()}"
        )
    if frame["video_name"].nunique() != 16:
        raise AuditError(
            f"Expected 16 exact videos, found {frame['video_name'].nunique()}"
        )

    for task in TASKS:
        column = f"after_{task}"
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not values.between(1, 9).all():
            raise AuditError(f"Invalid 1-9 values in {column}")
        frame[column] = values.astype(int)

    labels: dict[tuple[str, str], np.ndarray] = {}
    label_capacity_rows: list[dict[str, Any]] = []
    for task in TASKS:
        for policy in POLICIES:
            target = make_binary(frame[f"after_{task}"], policy)
            labels[(task, policy)] = target
            retained = int((target >= 0).sum())
            label_capacity_rows.append(
                {
                    "task": task,
                    "policy": policy,
                    "available_rows": int(len(target)),
                    "retained_rows": retained,
                    "discarded_rows": int(len(target) - retained),
                    "retention_fraction": retained / len(target),
                    "low_count": int((target == 0).sum()),
                    "high_count": int((target == 1).sum()),
                    "majority_accuracy": (
                        max(
                            int((target == 0).sum()),
                            int((target == 1).sum()),
                        )
                        / retained
                        if retained
                        else None
                    ),
                }
            )

    preferred_retention_ok = all(
        int((labels[(task, PREFERRED_POLICY)] >= 0).sum()) / len(frame)
        >= PRIMARY_POLICY_MIN_GLOBAL_RETENTION
        for task in TASKS
    )

    participants = sorted(frame["participant_id"].astype(str).unique())
    videos = sorted(frame["video_name"].astype(str).unique())
    participant_to_index = {
        participant: index
        for index, participant in enumerate(participants)
    }
    video_to_index = {
        video: index
        for index, video in enumerate(videos)
    }
    row_participant_index = (
        frame["participant_id"]
        .astype(str)
        .map(participant_to_index)
        .to_numpy(dtype=int)
    )
    row_video_index = (
        frame["video_name"]
        .astype(str)
        .map(video_to_index)
        .to_numpy(dtype=int)
    )

    scheme_trial_rows: list[dict[str, Any]] = []
    scheme_summaries: list[dict[str, Any]] = []

    print(
        f"Running {args.random_partitions} label-blind partitions "
        f"for each of {len(SCHEMES)} schemes..."
    )

    for subject_folds, video_folds in SCHEMES:
        scheme_name = f"{subject_folds}x{video_folds}"
        minimal_flags: list[bool] = []
        strong_flags: list[bool] = []
        raw_min_values: list[int] = []
        preferred_v_both: list[float] = []
        preferred_a_both: list[float] = []
        preferred_v_min_retained: list[int] = []
        preferred_a_min_retained: list[int] = []
        raw_empty_values: list[int] = []

        for partition_index in range(args.random_partitions):
            subject_seed = derived_seed(
                manifest_hash,
                "robustness",
                scheme_name,
                partition_index,
                "subjects",
            )
            video_seed = derived_seed(
                manifest_hash,
                "robustness",
                scheme_name,
                partition_index,
                "videos",
            )
            participant_fold = assignment_from_seed(
                len(participants),
                subject_folds,
                subject_seed,
            )
            video_fold = assignment_from_seed(
                len(videos),
                video_folds,
                video_seed,
            )
            evaluation = evaluate_partition(
                participant_fold,
                video_fold,
                row_participant_index,
                row_video_index,
                labels,
            )

            minimal_flags.append(evaluation.minimal_pass)
            strong_flags.append(evaluation.strong_pass)
            raw_min_values.append(evaluation.min_raw_test_rows)
            raw_empty_values.append(evaluation.raw_empty_cells)

            v_pref = evaluation.policy_metrics[
                ("valence", PREFERRED_POLICY)
            ]
            a_pref = evaluation.policy_metrics[
                ("arousal", PREFERRED_POLICY)
            ]
            preferred_v_both.append(v_pref.both_class_cell_fraction)
            preferred_a_both.append(a_pref.both_class_cell_fraction)
            preferred_v_min_retained.append(v_pref.min_retained_test_rows)
            preferred_a_min_retained.append(a_pref.min_retained_test_rows)

            row: dict[str, Any] = {
                "scheme": scheme_name,
                "subject_folds": subject_folds,
                "video_folds": video_folds,
                "outer_cells": subject_folds * video_folds,
                "partition_index": partition_index,
                "subject_seed": subject_seed,
                "video_seed": video_seed,
                "minimal_pass": evaluation.minimal_pass,
                "strong_pass": evaluation.strong_pass,
                "raw_empty_cells": evaluation.raw_empty_cells,
                "min_raw_test_rows": evaluation.min_raw_test_rows,
                "median_raw_test_rows": evaluation.median_raw_test_rows,
                "max_raw_test_rows": evaluation.max_raw_test_rows,
            }
            for task in TASKS:
                metric = evaluation.policy_metrics[
                    (task, PREFERRED_POLICY)
                ]
                prefix = f"{task}_{PREFERRED_POLICY}"
                row[f"{prefix}_empty_cells"] = metric.empty_test_cells
                row[f"{prefix}_one_class_cells"] = (
                    metric.one_class_test_cells
                )
                row[f"{prefix}_both_class_fraction"] = (
                    metric.both_class_cell_fraction
                )
                row[f"{prefix}_min_test_rows"] = (
                    metric.min_retained_test_rows
                )
                row[f"{prefix}_min_train_class"] = (
                    metric.min_train_class_count
                )
            scheme_trial_rows.append(row)

        minimal_pass_rate = float(np.mean(minimal_flags))
        strong_pass_rate = float(np.mean(strong_flags))
        robust_candidate = bool(
            preferred_retention_ok
            and minimal_pass_rate >= ROBUST_MINIMAL_PASS_RATE
            and percentile(raw_min_values, 0.05)
            >= MINIMAL_MIN_RAW_TEST_ROWS
        )

        scheme_summaries.append(
            {
                "scheme": scheme_name,
                "subject_folds": subject_folds,
                "video_folds": video_folds,
                "outer_cells": subject_folds * video_folds,
                "random_partitions": args.random_partitions,
                "minimal_pass_rate": minimal_pass_rate,
                "strong_pass_rate": strong_pass_rate,
                "raw_empty_cells_rate": float(
                    np.mean(np.asarray(raw_empty_values) > 0)
                ),
                "min_raw_test_rows_p05": percentile(
                    raw_min_values, 0.05
                ),
                "min_raw_test_rows_median": percentile(
                    raw_min_values, 0.50
                ),
                "min_raw_test_rows_p95": percentile(
                    raw_min_values, 0.95
                ),
                "preferred_valence_both_class_fraction_p05": percentile(
                    preferred_v_both, 0.05
                ),
                "preferred_valence_both_class_fraction_median": percentile(
                    preferred_v_both, 0.50
                ),
                "preferred_arousal_both_class_fraction_p05": percentile(
                    preferred_a_both, 0.05
                ),
                "preferred_arousal_both_class_fraction_median": percentile(
                    preferred_a_both, 0.50
                ),
                "preferred_valence_min_test_rows_p05": percentile(
                    preferred_v_min_retained, 0.05
                ),
                "preferred_arousal_min_test_rows_p05": percentile(
                    preferred_a_min_retained, 0.05
                ),
                "robust_candidate": robust_candidate,
            }
        )
        print(
            f"{scheme_name}: minimal_pass={minimal_pass_rate:.3f}, "
            f"strong_pass={strong_pass_rate:.3f}, "
            f"p05_min_raw={percentile(raw_min_values, 0.05):.2f}, "
            f"robust={robust_candidate}"
        )

    scheme_summary_df = pd.DataFrame(scheme_summaries)
    robust = scheme_summary_df[
        scheme_summary_df["robust_candidate"]
    ].copy()

    if robust.empty:
        ranked = scheme_summary_df.sort_values(
            [
                "minimal_pass_rate",
                "outer_cells",
                "strong_pass_rate",
            ],
            ascending=[False, False, False],
        )
        selected_row = ranked.iloc[0]
        scheme_selection_status = "NO_SCHEME_MET_ROBUSTNESS_GATE"
    else:
        ranked = robust.sort_values(
            [
                "outer_cells",
                "minimal_pass_rate",
                "strong_pass_rate",
            ],
            ascending=[False, False, False],
        )
        selected_row = ranked.iloc[0]
        scheme_selection_status = "ROBUST_SCHEME_SELECTED"

    selected_subject_folds = int(selected_row["subject_folds"])
    selected_video_folds = int(selected_row["video_folds"])
    selected_scheme = str(selected_row["scheme"])

    repeated_assignment_rows: list[dict[str, Any]] = []
    repeated_support_rows: list[dict[str, Any]] = []
    repetition_results: list[dict[str, Any]] = []

    print(
        f"Selected candidate scheme: {selected_scheme} "
        f"({scheme_selection_status})"
    )

    for repetition in range(args.repetitions):
        subject_seed = derived_seed(
            manifest_hash,
            "frozen_repetition",
            selected_scheme,
            repetition,
            "subjects",
        )
        video_seed = derived_seed(
            manifest_hash,
            "frozen_repetition",
            selected_scheme,
            repetition,
            "videos",
        )
        participant_fold = assignment_from_seed(
            len(participants),
            selected_subject_folds,
            subject_seed,
        )
        video_fold = assignment_from_seed(
            len(videos),
            selected_video_folds,
            video_seed,
        )
        evaluation = evaluate_partition(
            participant_fold,
            video_fold,
            row_participant_index,
            row_video_index,
            labels,
        )

        repetition_results.append(
            {
                "repetition": repetition,
                "role": "primary" if repetition == 0 else "sensitivity",
                "subject_seed": subject_seed,
                "video_seed": video_seed,
                "minimal_pass": evaluation.minimal_pass,
                "strong_pass": evaluation.strong_pass,
                "raw_empty_cells": evaluation.raw_empty_cells,
                "min_raw_test_rows": evaluation.min_raw_test_rows,
                "median_raw_test_rows": evaluation.median_raw_test_rows,
                "max_raw_test_rows": evaluation.max_raw_test_rows,
                "valence_both_class_fraction": evaluation.policy_metrics[
                    ("valence", PREFERRED_POLICY)
                ].both_class_cell_fraction,
                "arousal_both_class_fraction": evaluation.policy_metrics[
                    ("arousal", PREFERRED_POLICY)
                ].both_class_cell_fraction,
                "valence_min_retained_test_rows": (
                    evaluation.policy_metrics[
                        ("valence", PREFERRED_POLICY)
                    ].min_retained_test_rows
                ),
                "arousal_min_retained_test_rows": (
                    evaluation.policy_metrics[
                        ("arousal", PREFERRED_POLICY)
                    ].min_retained_test_rows
                ),
            }
        )

        for participant_index, participant in enumerate(participants):
            participant_rows = frame[
                frame["participant_id"].astype(str) == participant
            ]
            repeated_assignment_rows.append(
                {
                    "entity_type": "participant",
                    "entity_id": participant,
                    "repetition": repetition,
                    "role": (
                        "primary"
                        if repetition == 0
                        else "sensitivity"
                    ),
                    "fold": int(participant_fold[participant_index]) + 1,
                    "participant_sessions": int(
                        participant_rows[
                            "participant_session_key"
                        ].nunique()
                    ),
                    "observed_emotional_presentations": int(
                        len(participant_rows)
                    ),
                    "seed": subject_seed,
                }
            )

        for video_index, video in enumerate(videos):
            video_rows = frame[
                frame["video_name"].astype(str) == video
            ]
            repeated_assignment_rows.append(
                {
                    "entity_type": "video",
                    "entity_id": video,
                    "repetition": repetition,
                    "role": (
                        "primary"
                        if repetition == 0
                        else "sensitivity"
                    ),
                    "fold": int(video_fold[video_index]) + 1,
                    "participant_sessions": int(
                        video_rows[
                            "participant_session_key"
                        ].nunique()
                    ),
                    "observed_emotional_presentations": int(
                        len(video_rows)
                    ),
                    "seed": video_seed,
                }
            )

        for subject_fold_id in range(selected_subject_folds):
            held_subjects = {
                participants[index]
                for index in range(len(participants))
                if participant_fold[index] == subject_fold_id
            }
            subject_held = (
                frame["participant_id"].astype(str).isin(held_subjects)
            ).to_numpy()
            for video_fold_id in range(selected_video_folds):
                held_videos = {
                    videos[index]
                    for index in range(len(videos))
                    if video_fold[index] == video_fold_id
                }
                video_held = (
                    frame["video_name"].astype(str).isin(held_videos)
                ).to_numpy()
                test_mask = subject_held & video_held
                train_mask = (~subject_held) & (~video_held)
                cell_id = (
                    f"R{repetition:02d}_"
                    f"S{subject_fold_id + 1}_"
                    f"V{video_fold_id + 1}"
                )

                for task in TASKS:
                    for policy in POLICIES:
                        target = labels[(task, policy)]
                        test_labels = target[test_mask]
                        test_labels = test_labels[test_labels >= 0]
                        train_labels = target[train_mask]
                        train_labels = train_labels[train_labels >= 0]

                        repeated_support_rows.append(
                            {
                                "repetition": repetition,
                                "role": (
                                    "primary"
                                    if repetition == 0
                                    else "sensitivity"
                                ),
                                "scheme": selected_scheme,
                                "cell_id": cell_id,
                                "subject_fold": subject_fold_id + 1,
                                "video_fold": video_fold_id + 1,
                                "held_out_participants": ";".join(
                                    sorted(held_subjects)
                                ),
                                "held_out_videos": ";".join(
                                    sorted(held_videos)
                                ),
                                "task": task,
                                "policy": policy,
                                "raw_test_rows": int(test_mask.sum()),
                                "retained_test_rows": int(
                                    test_labels.size
                                ),
                                "test_low": int(
                                    (test_labels == 0).sum()
                                ),
                                "test_high": int(
                                    (test_labels == 1).sum()
                                ),
                                "test_both_classes": bool(
                                    np.unique(test_labels).size == 2
                                ),
                                "train_rows": int(train_mask.sum()),
                                "retained_train_rows": int(
                                    train_labels.size
                                ),
                                "train_low": int(
                                    (train_labels == 0).sum()
                                ),
                                "train_high": int(
                                    (train_labels == 1).sum()
                                ),
                                "train_both_classes": bool(
                                    np.unique(train_labels).size == 2
                                ),
                            }
                        )

        print(
            f"rep{repetition:02d} "
            f"({'primary' if repetition == 0 else 'sensitivity'}): "
            f"minimal={evaluation.minimal_pass}, "
            f"strong={evaluation.strong_pass}, "
            f"min_raw={evaluation.min_raw_test_rows}, "
            f"V_both={evaluation.policy_metrics[('valence', PREFERRED_POLICY)].both_class_cell_fraction:.3f}, "
            f"A_both={evaluation.policy_metrics[('arousal', PREFERRED_POLICY)].both_class_cell_fraction:.3f}"
        )

    primary_result = repetition_results[0]
    all_minimal = all(row["minimal_pass"] for row in repetition_results)
    primary_strong = bool(primary_result["strong_pass"])
    primary_minimal = bool(primary_result["minimal_pass"])

    if (
        scheme_selection_status == "ROBUST_SCHEME_SELECTED"
        and preferred_retention_ok
        and primary_strong
        and all_minimal
    ):
        protocol_decision = "LOCK_LABEL_BLIND_REPEATED_PROTOCOL"
    elif (
        scheme_selection_status == "ROBUST_SCHEME_SELECTED"
        and preferred_retention_ok
        and primary_minimal
        and all_minimal
    ):
        protocol_decision = "LOCK_WITH_CAPACITY_CAUTION"
    else:
        protocol_decision = "DO_NOT_LOCK_PROTOCOL"

    trials_df = pd.DataFrame(scheme_trial_rows)
    assignments_df = pd.DataFrame(repeated_assignment_rows)
    repeated_support_df = pd.DataFrame(repeated_support_rows)
    label_capacity_df = pd.DataFrame(label_capacity_rows)

    trials_path = output_paths[0]
    summary_path = output_paths[1]
    report_path = output_paths[2]
    json_path = output_paths[3]
    repeated_support_path = output_paths[4]
    protocol_path = output_paths[5]
    repeated_assignments_path = output_paths[6]
    primary_subject_path = output_paths[7]
    primary_video_path = output_paths[8]

    trials_df.to_csv(trials_path, index=False)
    scheme_summary_df.to_csv(summary_path, index=False)
    repeated_support_df.to_csv(repeated_support_path, index=False)
    assignments_df.to_csv(repeated_assignments_path, index=False)

    assignments_df[
        (assignments_df["repetition"] == 0)
        & (assignments_df["entity_type"] == "participant")
    ].to_csv(primary_subject_path, index=False)

    assignments_df[
        (assignments_df["repetition"] == 0)
        & (assignments_df["entity_type"] == "video")
    ].to_csv(primary_video_path, index=False)

    protocol = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(source_path),
        "source_manifest_sha256": manifest_hash,
        "cohort": "Cohort_B_Paired_EEG_EMG_Strict",
        "participants": len(participants),
        "participant_sessions": int(
            frame["participant_session_key"].nunique()
        ),
        "emotional_presentations": len(frame),
        "exact_videos": len(videos),
        "statistical_unit": "one emotional stimulus presentation",
        "content_identity": "exact VIDEO_NAME",
        "fold_construction_uses_labels": False,
        "fold_construction_uses_eeg_or_emg": False,
        "rerolling_allowed": False,
        "preferred_label_policy": {
            "policy": PREFERRED_POLICY,
            "rating_time": "after",
            "reason": (
                "Score 5 is treated as ambiguous and removed. "
                "The same predeclared rule is used for valence and arousal."
            ),
            "minimum_required_global_retention": (
                PRIMARY_POLICY_MIN_GLOBAL_RETENTION
            ),
            "retention_gate_passed": preferred_retention_ok,
            "other_policies_role": "sensitivity analyses",
        },
        "label_capacity": label_capacity_rows,
        "schemes_evaluated": [
            f"{subject_folds}x{video_folds}"
            for subject_folds, video_folds in SCHEMES
        ],
        "random_partitions_per_scheme": args.random_partitions,
        "scheme_selection_gate": {
            "minimum_minimal_pass_rate": ROBUST_MINIMAL_PASS_RATE,
            "minimum_p05_raw_test_rows": MINIMAL_MIN_RAW_TEST_ROWS,
            "selection_rule": (
                "Choose the largest Cartesian scheme meeting all "
                "predeclared robustness gates. Break ties by higher "
                "minimal-pass and strong-pass rates."
            ),
        },
        "scheme_selection_status": scheme_selection_status,
        "selected_scheme": selected_scheme,
        "selected_subject_folds": selected_subject_folds,
        "selected_video_folds": selected_video_folds,
        "outer_cells_per_repetition": (
            selected_subject_folds * selected_video_folds
        ),
        "repetitions": args.repetitions,
        "repetition_roles": {
            "0": "primary",
            "1-4": "sensitivity",
        },
        "repetition_results": repetition_results,
        "protocol_decision": protocol_decision,
        "gates": {
            "minimal": {
                "all_raw_cells_nonempty": True,
                "minimum_raw_test_rows": MINIMAL_MIN_RAW_TEST_ROWS,
                "minimum_retained_test_rows": (
                    MINIMAL_MIN_RETAINED_TEST_ROWS
                ),
                "minimum_train_class_count": MINIMAL_MIN_TRAIN_CLASS,
                "minimum_both_class_test_cell_fraction": (
                    MINIMAL_BOTH_CLASS_CELL_FRACTION
                ),
            },
            "strong": {
                "all_raw_cells_nonempty": True,
                "minimum_raw_test_rows": STRONG_MIN_RAW_TEST_ROWS,
                "minimum_retained_test_rows": (
                    STRONG_MIN_RETAINED_TEST_ROWS
                ),
                "minimum_train_class_count": STRONG_MIN_TRAIN_CLASS,
                "minimum_both_class_test_cell_fraction": (
                    STRONG_BOTH_CLASS_CELL_FRACTION
                ),
            },
        },
        "outputs": [str(path) for path in output_paths],
    }
    protocol_path.write_text(
        json.dumps(json_safe(protocol), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            json_safe(
                {
                    "protocol": protocol,
                    "scheme_summary": scheme_summaries,
                }
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    lines = [
        "# DEJA-VU Label-Blind Joint Subject-Stimulus CV Audit",
        "",
        f"Generated: `{protocol['generated_at_utc']}`",
        "",
        "No EEG/EMG model was trained. Fold construction used only "
        "participant identity, exact `VIDEO_NAME`, deterministic hashing, "
        "and balanced fold capacities. Labels were used only after each "
        "partition was fixed to audit feasibility.",
        "",
        "## Cohort",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Participants | {len(participants)} |",
        f"| Participant-sessions | {frame['participant_session_key'].nunique()} |",
        f"| Emotional presentations | {len(frame)} |",
        f"| Exact videos | {len(videos)} |",
        f"| Manifest SHA-256 | `{manifest_hash}` |",
        "",
        "## Label-policy capacity",
        "",
        "| Task | Policy | Retained | Discarded | Low | High | "
        "Majority accuracy |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in label_capacity_rows:
        lines.append(
            f"| {row['task']} | {row['policy']} | "
            f"{row['retained_rows']} | {row['discarded_rows']} | "
            f"{row['low_count']} | {row['high_count']} | "
            f"{row['majority_accuracy']:.4f} |"
        )

    lines.extend(
        [
            "",
            "Primary policy preference is `discard_midpoint` for both "
            "valence and arousal. It is accepted only if each task retains "
            f"at least {PRIMARY_POLICY_MIN_GLOBAL_RETENTION:.0%} of Cohort B.",
            "",
            f"Retention gate passed: `{preferred_retention_ok}`.",
            "",
            "## Label-blind scheme robustness",
            "",
            "| Scheme | Cells | Minimal pass rate | Strong pass rate | "
            "P05 min raw test | P05 V both-class fraction | "
            "P05 A both-class fraction | Robust candidate |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in scheme_summary_df.iterrows():
        lines.append(
            f"| {row['scheme']} | {int(row['outer_cells'])} | "
            f"{row['minimal_pass_rate']:.4f} | "
            f"{row['strong_pass_rate']:.4f} | "
            f"{row['min_raw_test_rows_p05']:.2f} | "
            f"{row['preferred_valence_both_class_fraction_p05']:.3f} | "
            f"{row['preferred_arousal_both_class_fraction_p05']:.3f} | "
            f"{bool(row['robust_candidate'])} |"
        )

    lines.extend(
        [
            "",
            "## Selected candidate scheme",
            "",
            f"- Selection status: **{scheme_selection_status}**",
            f"- Scheme: **{selected_scheme}**",
            f"- Outer cells per repetition: "
            f"`{selected_subject_folds * selected_video_folds}`",
            "- Scheme selection used robustness distributions from "
            "label-blind partitions, not neural-model performance.",
            "",
            "## Hash-derived repeated protocol",
            "",
            "| Repetition | Role | Minimal | Strong | Min raw test | "
            "Valence both-class cells | Arousal both-class cells |",
            "|---:|---|---|---|---:|---:|---:|",
        ]
    )
    n_selected_cells = selected_subject_folds * selected_video_folds
    for row in repetition_results:
        lines.append(
            f"| {row['repetition']} | {row['role']} | "
            f"{row['minimal_pass']} | {row['strong_pass']} | "
            f"{row['min_raw_test_rows']} | "
            f"{row['valence_both_class_fraction'] * n_selected_cells:.0f}"
            f"/{n_selected_cells} | "
            f"{row['arousal_both_class_fraction'] * n_selected_cells:.0f}"
            f"/{n_selected_cells} |"
        )

    lines.extend(
        [
            "",
            "No repetition was rerolled, removed, or replaced.",
            "",
            "## Decision",
            "",
            f"**{protocol_decision}**",
            "",
            "Interpretation:",
            "",
            "- `LOCK_LABEL_BLIND_REPEATED_PROTOCOL`: primary repetition "
            "passes the strong gate and every sensitivity repetition passes "
            "the minimal gate.",
            "- `LOCK_WITH_CAPACITY_CAUTION`: primary and all sensitivity "
            "repetitions pass only the minimal gate.",
            "- `DO_NOT_LOCK_PROTOCOL`: the selected scheme or repeated "
            "partitions do not meet the preregistered capacity requirements.",
            "",
            "## Important metric rule",
            "",
            "Because DEJA-VU is a sparse participant-video graph, some test "
            "cells may contain only one class even when the pooled repetition "
            "contains both classes. Future headline metrics must therefore "
            "be pooled over the complete repetition with participant/video-"
            "aware uncertainty. Cell-level Balanced Accuracy or ROC-AUC must "
            "not be reported for one-class cells.",
            "",
            "## Outputs",
            "",
        ]
    )
    for path in output_paths:
        lines.append(f"- `{path.relative_to(repo_root)}`")

    lines.extend(
        [
            "",
            "## Next stage",
            "",
            "Only after this report is reviewed and the decision is accepted "
            "should the candidate files be renamed/frozen, committed, and "
            "used for shortcut/null audits. No model training is authorized "
            "by this script.",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nDEJA-VU LABEL-BLIND JOINT CV CHECKPOINT")
    print(f"Manifest SHA-256: {manifest_hash}")
    print(f"Preferred label policy: {PREFERRED_POLICY}")
    print(f"Preferred-policy retention gate: {preferred_retention_ok}")
    print(f"Scheme selection: {scheme_selection_status}")
    print(f"Selected scheme: {selected_scheme}")
    print(f"Protocol decision: {protocol_decision}")
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

