#!/usr/bin/env python3
"""DEJA-VU MM-SAGE-DG gradient-support capacity audit.

This audit does not train a model and does not compute physiological gradients.
It answers the prerequisite data-capacity question:

For every frozen Joint Subject–Exact-Video outer split, task, and class,
how many source participants can contribute a class-conditional gradient under
three eligibility definitions?

Weak:
    >= 1 scored trial for the subject-class.

Minimal:
    >= 2 scored trials for the subject-class.

Strong content-diverse:
    >= 2 scored trials from >= 2 exact VIDEO_NAME identities for the
    subject-class.

The audit also evaluates the capacity loss caused by leakage-safe source
validation using the already frozen 3x3 subject/video folds:

- outer_source:
    both remaining subject folds x both remaining video folds;
- inner_subject_only:
    one source subject fold x both source video folds;
- inner_video_only:
    both source subject folds x one source video fold;
- inner_joint:
    one source subject fold x one source video fold.

No fold is rerolled, no midpoint policy is changed, and no test information is
used to improve capacity.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


TASKS = ("valence", "arousal")
CLASSES = ((0, "low"), (1, "high"))
ELIGIBILITY_LEVELS = (
    ("weak_1trial", 1, 1),
    ("minimal_2trials", 2, 1),
    ("strong_2trials_2videos", 2, 2),
)
EXPECTED_REPETITIONS = (0, 1, 2, 3, 4)
EXPECTED_SUBJECT_FOLDS = (1, 2, 3)
EXPECTED_VIDEO_FOLDS = (1, 2, 3)
MIN_CONSENSUS_SUBJECTS = 3


class AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class Scenario:
    repetition: int
    held_subject_fold: int
    held_video_fold: int
    scenario_type: str
    scenario_id: str
    train_subject_folds: tuple[int, ...]
    train_video_folds: tuple[int, ...]
    validation_subject_folds: tuple[int, ...]
    validation_video_folds: tuple[int, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Atomically replace outputs from a previous identical audit.",
    )
    return parser.parse_args()


def git_value(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return completed.stdout.strip()
    except Exception:
        return "unavailable"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.ndarray):
        return [json_safe(v) for v in value.tolist()]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_text(path: Path, text: str, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise AuditError(
            f"Output already exists: {path}\n"
            "Rerun with --overwrite only when you intentionally want to "
            "regenerate this deterministic audit."
        )
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def atomic_write_csv(
    frame: pd.DataFrame,
    path: Path,
    overwrite: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise AuditError(
            f"Output already exists: {path}\n"
            "Rerun with --overwrite only when you intentionally want to "
            "regenerate this deterministic audit."
        )
    temp = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temp, index=False)
    os.replace(temp, path)


def derive_primary_label(frame: pd.DataFrame, task: str) -> pd.Series:
    preferred = f"primary_{task}_label"
    if preferred in frame.columns:
        numeric = pd.to_numeric(frame[preferred], errors="coerce")
        invalid = numeric.dropna()[~numeric.dropna().isin([0, 1])]
        if not invalid.empty:
            raise AuditError(
                f"{preferred} contains values other than 0, 1, or missing."
            )
        return numeric.astype("Float64")

    score_col = f"after_{task}"
    if score_col not in frame.columns:
        raise AuditError(
            f"Neither {preferred} nor {score_col} exists in the label manifest."
        )
    score = pd.to_numeric(frame[score_col], errors="coerce")
    if score.isna().any() or not score.between(1, 9).all():
        raise AuditError(f"Invalid 1-9 scores in {score_col}.")
    return pd.Series(
        np.where(score < 5, 0, np.where(score > 5, 1, np.nan)),
        index=frame.index,
        dtype="Float64",
    )


def validate_and_prepare_labels(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "participant_id",
        "participant_session_key",
        "video_name",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise AuditError(f"Label manifest is missing columns: {missing}")

    prepared = frame.copy()
    prepared["participant_id"] = prepared["participant_id"].astype(str)
    prepared["participant_session_key"] = (
        prepared["participant_session_key"].astype(str)
    )
    prepared["video_name"] = prepared["video_name"].astype(str)

    for task in TASKS:
        prepared[f"_label_{task}"] = derive_primary_label(prepared, task)

    if len(prepared) != 90:
        raise AuditError(f"Expected 90 Cohort-B emotional rows, found {len(prepared)}.")
    if prepared["participant_id"].nunique() != 24:
        raise AuditError(
            f"Expected 24 Cohort-B participants, found "
            f"{prepared['participant_id'].nunique()}."
        )
    if prepared["participant_session_key"].nunique() != 30:
        raise AuditError(
            f"Expected 30 Cohort-B participant-sessions, found "
            f"{prepared['participant_session_key'].nunique()}."
        )
    if prepared["video_name"].nunique() != 16:
        raise AuditError(
            f"Expected 16 exact emotional videos, found "
            f"{prepared['video_name'].nunique()}."
        )

    expected = {
        "valence": (75, 53, 22),
        "arousal": (71, 33, 38),
    }
    for task, (retained, low, high) in expected.items():
        labels = prepared[f"_label_{task}"]
        observed = (
            int(labels.notna().sum()),
            int((labels == 0).sum()),
            int((labels == 1).sum()),
        )
        if observed != (retained, low, high):
            raise AuditError(
                f"Unexpected {task} support {observed}; "
                f"expected {(retained, low, high)}."
            )

    return prepared


def validate_assignments(assignments: pd.DataFrame) -> pd.DataFrame:
    required = {"entity_type", "entity_id", "repetition", "fold"}
    missing = sorted(required - set(assignments.columns))
    if missing:
        raise AuditError(f"Fold assignments are missing columns: {missing}")

    result = assignments.copy()
    result["entity_type"] = result["entity_type"].astype(str)
    result["entity_id"] = result["entity_id"].astype(str)
    result["repetition"] = pd.to_numeric(
        result["repetition"], errors="raise"
    ).astype(int)
    result["fold"] = pd.to_numeric(result["fold"], errors="raise").astype(int)

    if sorted(result["repetition"].unique().tolist()) != list(
        EXPECTED_REPETITIONS
    ):
        raise AuditError("Expected repetitions 0-4 in frozen assignments.")

    for repetition in EXPECTED_REPETITIONS:
        subset = result[result["repetition"] == repetition]
        participants = subset[subset["entity_type"] == "participant"]
        videos = subset[subset["entity_type"] == "video"]

        if len(participants) != 24 or participants["entity_id"].nunique() != 24:
            raise AuditError(
                f"Repetition {repetition}: expected 24 participant assignments."
            )
        if len(videos) != 16 or videos["entity_id"].nunique() != 16:
            raise AuditError(
                f"Repetition {repetition}: expected 16 video assignments."
            )
        if sorted(participants["fold"].unique().tolist()) != [1, 2, 3]:
            raise AuditError(
                f"Repetition {repetition}: subject folds are not 1,2,3."
            )
        if sorted(videos["fold"].unique().tolist()) != [1, 2, 3]:
            raise AuditError(
                f"Repetition {repetition}: video folds are not 1,2,3."
            )

    return result


def fold_maps(
    assignments: pd.DataFrame,
    repetition: int,
) -> tuple[dict[str, int], dict[str, int]]:
    subset = assignments[assignments["repetition"] == repetition]
    participant_map = {
        str(row.entity_id): int(row.fold)
        for row in subset[subset["entity_type"] == "participant"].itertuples()
    }
    video_map = {
        str(row.entity_id): int(row.fold)
        for row in subset[subset["entity_type"] == "video"].itertuples()
    }
    return participant_map, video_map


def build_scenarios(
    repetition: int,
    held_subject_fold: int,
    held_video_fold: int,
) -> list[Scenario]:
    source_subject_folds = tuple(
        fold for fold in EXPECTED_SUBJECT_FOLDS if fold != held_subject_fold
    )
    source_video_folds = tuple(
        fold for fold in EXPECTED_VIDEO_FOLDS if fold != held_video_fold
    )
    scenarios: list[Scenario] = [
        Scenario(
            repetition=repetition,
            held_subject_fold=held_subject_fold,
            held_video_fold=held_video_fold,
            scenario_type="outer_source",
            scenario_id=(
                f"R{repetition:02d}_S{held_subject_fold}_V{held_video_fold}"
                "_outer_source"
            ),
            train_subject_folds=source_subject_folds,
            train_video_folds=source_video_folds,
            validation_subject_folds=(),
            validation_video_folds=(),
        )
    ]

    for train_subject_fold in source_subject_folds:
        validation_subject_fold = tuple(
            fold
            for fold in source_subject_folds
            if fold != train_subject_fold
        )
        scenarios.append(
            Scenario(
                repetition=repetition,
                held_subject_fold=held_subject_fold,
                held_video_fold=held_video_fold,
                scenario_type="inner_subject_only",
                scenario_id=(
                    f"R{repetition:02d}_S{held_subject_fold}_V{held_video_fold}"
                    f"_inner_subject_train_S{train_subject_fold}"
                ),
                train_subject_folds=(train_subject_fold,),
                train_video_folds=source_video_folds,
                validation_subject_folds=validation_subject_fold,
                validation_video_folds=(),
            )
        )

    for train_video_fold in source_video_folds:
        validation_video_fold = tuple(
            fold for fold in source_video_folds if fold != train_video_fold
        )
        scenarios.append(
            Scenario(
                repetition=repetition,
                held_subject_fold=held_subject_fold,
                held_video_fold=held_video_fold,
                scenario_type="inner_video_only",
                scenario_id=(
                    f"R{repetition:02d}_S{held_subject_fold}_V{held_video_fold}"
                    f"_inner_video_train_V{train_video_fold}"
                ),
                train_subject_folds=source_subject_folds,
                train_video_folds=(train_video_fold,),
                validation_subject_folds=(),
                validation_video_folds=validation_video_fold,
            )
        )

    for train_subject_fold in source_subject_folds:
        for train_video_fold in source_video_folds:
            validation_subject_fold = tuple(
                fold
                for fold in source_subject_folds
                if fold != train_subject_fold
            )
            validation_video_fold = tuple(
                fold
                for fold in source_video_folds
                if fold != train_video_fold
            )
            scenarios.append(
                Scenario(
                    repetition=repetition,
                    held_subject_fold=held_subject_fold,
                    held_video_fold=held_video_fold,
                    scenario_type="inner_joint",
                    scenario_id=(
                        f"R{repetition:02d}_S{held_subject_fold}"
                        f"_V{held_video_fold}"
                        f"_inner_joint_train_S{train_subject_fold}"
                        f"_V{train_video_fold}"
                    ),
                    train_subject_folds=(train_subject_fold,),
                    train_video_folds=(train_video_fold,),
                    validation_subject_folds=validation_subject_fold,
                    validation_video_folds=validation_video_fold,
                )
            )

    return scenarios


def comb_probability(total: int, eligible: int, sample_size: int = 3) -> float:
    if total < sample_size or eligible < sample_size:
        return 0.0
    return math.comb(eligible, sample_size) / math.comb(total, sample_size)


def pairwise_jaccard(video_sets: list[set[str]]) -> float | None:
    if len(video_sets) < 2:
        return None
    values: list[float] = []
    for first, second in itertools.combinations(video_sets, 2):
        union = first | second
        values.append(len(first & second) / len(union) if union else 0.0)
    return float(np.mean(values)) if values else None


def percentile(series: pd.Series, q: float) -> float:
    if series.empty:
        return float("nan")
    return float(np.quantile(series.to_numpy(dtype=float), q))


def analyse_scenario(
    data: pd.DataFrame,
    scenario: Scenario,
    participant_fold_map: dict[str, int],
    video_fold_map: dict[str, int],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    participant_fold = data["participant_id"].map(participant_fold_map)
    video_fold = data["video_name"].map(video_fold_map)
    if participant_fold.isna().any() or video_fold.isna().any():
        raise AuditError(
            f"Incomplete frozen assignment mapping in {scenario.scenario_id}."
        )

    train_mask = participant_fold.isin(scenario.train_subject_folds) & video_fold.isin(
        scenario.train_video_folds
    )
    train = data.loc[train_mask].copy()
    source_subjects = sorted(
        participant
        for participant, fold in participant_fold_map.items()
        if fold in scenario.train_subject_folds
    )
    source_videos = sorted(
        video
        for video, fold in video_fold_map.items()
        if fold in scenario.train_video_folds
    )

    if sorted(train["participant_id"].unique().tolist()) != sorted(
        set(train["participant_id"])
    ):
        raise AssertionError("Unexpected participant duplication check failure.")

    scenario_base = {
        "repetition": scenario.repetition,
        "held_subject_fold": scenario.held_subject_fold,
        "held_video_fold": scenario.held_video_fold,
        "outer_cell": (
            f"R{scenario.repetition:02d}_"
            f"S{scenario.held_subject_fold}_V{scenario.held_video_fold}"
        ),
        "scenario_type": scenario.scenario_type,
        "scenario_id": scenario.scenario_id,
        "train_subject_folds": ";".join(map(str, scenario.train_subject_folds)),
        "train_video_folds": ";".join(map(str, scenario.train_video_folds)),
        "validation_subject_folds": ";".join(
            map(str, scenario.validation_subject_folds)
        ),
        "validation_video_folds": ";".join(
            map(str, scenario.validation_video_folds)
        ),
        "nominal_train_subjects": len(source_subjects),
        "nominal_train_videos": len(source_videos),
        "observed_train_subjects": int(train["participant_id"].nunique()),
        "observed_train_videos": int(train["video_name"].nunique()),
        "raw_train_rows": int(len(train)),
    }

    subject_detail_rows: list[dict[str, Any]] = []
    capacity_rows: list[dict[str, Any]] = []
    class_pair_rows: list[dict[str, Any]] = []
    video_support_rows: list[dict[str, Any]] = []

    eligible_sets: dict[tuple[str, str, str], set[str]] = {}

    for task in TASKS:
        label_column = f"_label_{task}"
        for class_value, class_name in CLASSES:
            class_rows = train[train[label_column] == class_value].copy()
            grouped = (
                class_rows.groupby("participant_id", dropna=False)
                .agg(
                    trial_count=("video_name", "size"),
                    unique_video_count=("video_name", "nunique"),
                    unique_session_count=(
                        "participant_session_key",
                        "nunique",
                    ),
                )
                .reset_index()
            )
            participant_stats = {
                str(row.participant_id): {
                    "trial_count": int(row.trial_count),
                    "unique_video_count": int(row.unique_video_count),
                    "unique_session_count": int(row.unique_session_count),
                }
                for row in grouped.itertuples()
            }

            for participant_id in source_subjects:
                stats = participant_stats.get(
                    participant_id,
                    {
                        "trial_count": 0,
                        "unique_video_count": 0,
                        "unique_session_count": 0,
                    },
                )
                subject_videos = sorted(
                    class_rows.loc[
                        class_rows["participant_id"] == participant_id,
                        "video_name",
                    ].unique()
                )
                detail = {
                    **scenario_base,
                    "task": task,
                    "class_value": class_value,
                    "class_name": class_name,
                    "participant_id": participant_id,
                    "trial_count": stats["trial_count"],
                    "unique_video_count": stats["unique_video_count"],
                    "unique_session_count": stats["unique_session_count"],
                    "exact_videos": ";".join(subject_videos),
                }
                for level_name, min_trials, min_videos in ELIGIBILITY_LEVELS:
                    detail[f"eligible_{level_name}"] = bool(
                        stats["trial_count"] >= min_trials
                        and stats["unique_video_count"] >= min_videos
                    )
                subject_detail_rows.append(detail)

            class_video_group = (
                class_rows.groupby("video_name", dropna=False)
                .agg(
                    trial_count=("participant_id", "size"),
                    subject_count=("participant_id", "nunique"),
                    session_count=("participant_session_key", "nunique"),
                )
                .reset_index()
            )
            for row in class_video_group.itertuples():
                video_support_rows.append(
                    {
                        **scenario_base,
                        "task": task,
                        "class_value": class_value,
                        "class_name": class_name,
                        "video_name": str(row.video_name),
                        "trial_count": int(row.trial_count),
                        "subject_count": int(row.subject_count),
                        "session_count": int(row.session_count),
                    }
                )

            for level_name, min_trials, min_videos in ELIGIBILITY_LEVELS:
                eligible = {
                    participant_id
                    for participant_id, stats in participant_stats.items()
                    if stats["trial_count"] >= min_trials
                    and stats["unique_video_count"] >= min_videos
                }
                eligible_sets[(task, class_name, level_name)] = eligible

                eligible_stats = [
                    participant_stats[participant_id]
                    for participant_id in sorted(eligible)
                ]
                eligible_video_sets = [
                    set(
                        class_rows.loc[
                            class_rows["participant_id"] == participant_id,
                            "video_name",
                        ].astype(str)
                    )
                    for participant_id in sorted(eligible)
                ]
                union_videos = (
                    set().union(*eligible_video_sets)
                    if eligible_video_sets
                    else set()
                )
                common_videos = (
                    set.intersection(*eligible_video_sets)
                    if eligible_video_sets
                    else set()
                )

                class_video_counts = (
                    class_rows.groupby("video_name")["participant_id"]
                    .nunique()
                    .astype(int)
                )
                total_subjects = len(source_subjects)
                eligible_count = len(eligible)
                trio_probability = comb_probability(
                    total_subjects,
                    eligible_count,
                    MIN_CONSENSUS_SUBJECTS,
                )
                expected_attempts = (
                    1.0 / trio_probability
                    if trio_probability > 0
                    else None
                )

                capacity_rows.append(
                    {
                        **scenario_base,
                        "task": task,
                        "class_value": class_value,
                        "class_name": class_name,
                        "eligibility_level": level_name,
                        "minimum_trials": min_trials,
                        "minimum_exact_videos": min_videos,
                        "scored_class_trials": int(len(class_rows)),
                        "class_subjects_with_any_trial": int(
                            class_rows["participant_id"].nunique()
                        ),
                        "class_unique_videos": int(
                            class_rows["video_name"].nunique()
                        ),
                        "class_videos_with_ge3_subjects": int(
                            (class_video_counts >= 3).sum()
                        ),
                        "eligible_subject_count": eligible_count,
                        "eligible_subject_ids": ";".join(sorted(eligible)),
                        "consensus_M_ge_3": bool(
                            eligible_count >= MIN_CONSENSUS_SUBJECTS
                        ),
                        "eligible_fraction_of_nominal_subjects": (
                            eligible_count / total_subjects
                            if total_subjects
                            else None
                        ),
                        "uniform_random_trio_acceptance_probability": (
                            trio_probability
                        ),
                        "expected_uniform_resampling_attempts_for_valid_trio": (
                            expected_attempts
                        ),
                        "eligible_trial_count_min": (
                            min(
                                stats["trial_count"]
                                for stats in eligible_stats
                            )
                            if eligible_stats
                            else 0
                        ),
                        "eligible_trial_count_median": (
                            float(
                                np.median(
                                    [
                                        stats["trial_count"]
                                        for stats in eligible_stats
                                    ]
                                )
                            )
                            if eligible_stats
                            else 0.0
                        ),
                        "eligible_trial_count_max": (
                            max(
                                stats["trial_count"]
                                for stats in eligible_stats
                            )
                            if eligible_stats
                            else 0
                        ),
                        "eligible_video_count_min": (
                            min(
                                stats["unique_video_count"]
                                for stats in eligible_stats
                            )
                            if eligible_stats
                            else 0
                        ),
                        "eligible_video_count_median": (
                            float(
                                np.median(
                                    [
                                        stats["unique_video_count"]
                                        for stats in eligible_stats
                                    ]
                                )
                            )
                            if eligible_stats
                            else 0.0
                        ),
                        "eligible_video_count_max": (
                            max(
                                stats["unique_video_count"]
                                for stats in eligible_stats
                            )
                            if eligible_stats
                            else 0
                        ),
                        "eligible_subject_video_union_count": len(union_videos),
                        "eligible_subject_video_common_count": len(common_videos),
                        "eligible_subject_video_pairwise_jaccard_mean": (
                            pairwise_jaccard(eligible_video_sets)
                        ),
                    }
                )

        for level_name, _, _ in ELIGIBILITY_LEVELS:
            low_set = eligible_sets[(task, "low", level_name)]
            high_set = eligible_sets[(task, "high", level_name)]
            intersection = low_set & high_set
            union = low_set | high_set
            class_pair_rows.append(
                {
                    **scenario_base,
                    "task": task,
                    "eligibility_level": level_name,
                    "low_eligible_subjects": len(low_set),
                    "high_eligible_subjects": len(high_set),
                    "both_classes_eligible_subjects": len(intersection),
                    "both_classes_eligible_subject_ids": ";".join(
                        sorted(intersection)
                    ),
                    "either_class_eligible_subjects": len(union),
                    "low_high_subject_set_jaccard": (
                        len(intersection) / len(union) if union else None
                    ),
                    "same_subject_trio_for_both_classes_possible": bool(
                        len(intersection) >= MIN_CONSENSUS_SUBJECTS
                    ),
                }
            )

    return (
        subject_detail_rows,
        capacity_rows,
        class_pair_rows,
        video_support_rows,
    )


def aggregate_capacity(capacity: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [
        "scenario_type",
        "task",
        "class_name",
        "eligibility_level",
    ]
    for keys, subset in capacity.groupby(group_columns, dropna=False):
        (
            scenario_type,
            task,
            class_name,
            eligibility_level,
        ) = keys
        finite_attempts = pd.to_numeric(
            subset[
                "expected_uniform_resampling_attempts_for_valid_trio"
            ],
            errors="coerce",
        ).dropna()
        rows.append(
            {
                "scenario_type": scenario_type,
                "task": task,
                "class_name": class_name,
                "eligibility_level": eligibility_level,
                "configuration_count": int(len(subset)),
                "eligible_subjects_min": int(
                    subset["eligible_subject_count"].min()
                ),
                "eligible_subjects_p10": percentile(
                    subset["eligible_subject_count"], 0.10
                ),
                "eligible_subjects_median": float(
                    subset["eligible_subject_count"].median()
                ),
                "eligible_subjects_p90": percentile(
                    subset["eligible_subject_count"], 0.90
                ),
                "eligible_subjects_max": int(
                    subset["eligible_subject_count"].max()
                ),
                "configurations_with_M_lt_3": int(
                    (~subset["consensus_M_ge_3"].astype(bool)).sum()
                ),
                "M_ge_3_pass_rate": float(
                    subset["consensus_M_ge_3"].astype(bool).mean()
                ),
                "scored_class_trials_min": int(
                    subset["scored_class_trials"].min()
                ),
                "scored_class_trials_median": float(
                    subset["scored_class_trials"].median()
                ),
                "class_unique_videos_min": int(
                    subset["class_unique_videos"].min()
                ),
                "class_videos_with_ge3_subjects_min": int(
                    subset["class_videos_with_ge3_subjects"].min()
                ),
                "uniform_trio_acceptance_probability_median": float(
                    subset[
                        "uniform_random_trio_acceptance_probability"
                    ].median()
                ),
                "uniform_trio_acceptance_probability_min": float(
                    subset[
                        "uniform_random_trio_acceptance_probability"
                    ].min()
                ),
                "expected_resampling_attempts_max_finite": (
                    float(finite_attempts.max())
                    if not finite_attempts.empty
                    else None
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)


def aggregate_class_pairs(class_pairs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["scenario_type", "task", "eligibility_level"]
    for keys, subset in class_pairs.groupby(group_columns, dropna=False):
        scenario_type, task, eligibility_level = keys
        rows.append(
            {
                "scenario_type": scenario_type,
                "task": task,
                "eligibility_level": eligibility_level,
                "configuration_count": int(len(subset)),
                "both_classes_subjects_min": int(
                    subset["both_classes_eligible_subjects"].min()
                ),
                "both_classes_subjects_p10": percentile(
                    subset["both_classes_eligible_subjects"], 0.10
                ),
                "both_classes_subjects_median": float(
                    subset["both_classes_eligible_subjects"].median()
                ),
                "both_classes_subjects_max": int(
                    subset["both_classes_eligible_subjects"].max()
                ),
                "same_subject_trio_pass_rate": float(
                    subset[
                        "same_subject_trio_for_both_classes_possible"
                    ]
                    .astype(bool)
                    .mean()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(group_columns).reset_index(drop=True)


def task_gate_summary(
    capacity: pd.DataFrame,
    class_pairs: pd.DataFrame,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for task in TASKS:
        task_result: dict[str, Any] = {}
        for level_name, _, _ in ELIGIBILITY_LEVELS:
            outer = capacity[
                (capacity["scenario_type"] == "outer_source")
                & (capacity["task"] == task)
                & (capacity["eligibility_level"] == level_name)
            ]
            inner_joint = capacity[
                (capacity["scenario_type"] == "inner_joint")
                & (capacity["task"] == task)
                & (capacity["eligibility_level"] == level_name)
            ]
            outer_pairs = class_pairs[
                (class_pairs["scenario_type"] == "outer_source")
                & (class_pairs["task"] == task)
                & (class_pairs["eligibility_level"] == level_name)
            ]

            task_result[level_name] = {
                "outer_configurations": int(len(outer)),
                "outer_min_eligible_subjects_any_class": int(
                    outer["eligible_subject_count"].min()
                ),
                "outer_M_ge_3_pass_rate": float(
                    outer["consensus_M_ge_3"].astype(bool).mean()
                ),
                "outer_all_classes_all_cells_M_ge_3": bool(
                    outer["consensus_M_ge_3"].astype(bool).all()
                ),
                "inner_joint_M_ge_3_pass_rate": float(
                    inner_joint["consensus_M_ge_3"].astype(bool).mean()
                ),
                "outer_same_subject_both_classes_min": int(
                    outer_pairs["both_classes_eligible_subjects"].min()
                ),
                "outer_same_subject_trio_pass_rate": float(
                    outer_pairs[
                        "same_subject_trio_for_both_classes_possible"
                    ]
                    .astype(bool)
                    .mean()
                ),
            }

        weak = task_result["weak_1trial"]
        minimal = task_result["minimal_2trials"]
        strong = task_result["strong_2trials_2videos"]

        if (
            strong["outer_all_classes_all_cells_M_ge_3"]
            and strong["inner_joint_M_ge_3_pass_rate"] >= 0.80
            and strong["outer_same_subject_trio_pass_rate"] >= 0.80
        ):
            empirical_status = "ROBUST_FULL_MECHANISM_SUPPORT"
        elif strong["outer_all_classes_all_cells_M_ge_3"]:
            empirical_status = "OUTER_FIT_ONLY_STRONG_SUPPORT"
        elif minimal["outer_all_classes_all_cells_M_ge_3"]:
            empirical_status = "MINIMAL_MULTI_TRIAL_SUPPORT_ONLY"
        elif weak["outer_all_classes_all_cells_M_ge_3"]:
            empirical_status = "WEAK_SINGLE_TRIAL_SUPPORT_ONLY"
        else:
            empirical_status = "INSUFFICIENT_EVEN_FOR_WEAK_CONSENSUS_IN_ALL_CELLS"

        task_result["empirical_status"] = empirical_status
        result[task] = task_result

    statuses = [result[task]["empirical_status"] for task in TASKS]
    if all(status == "ROBUST_FULL_MECHANISM_SUPPORT" for status in statuses):
        overall = "ROBUST_FOR_BOTH_TASKS"
    elif all(
        status
        in {
            "ROBUST_FULL_MECHANISM_SUPPORT",
            "OUTER_FIT_ONLY_STRONG_SUPPORT",
        }
        for status in statuses
    ):
        overall = "OUTER_TRAINING_FEASIBLE_BUT_NESTED_VALIDATION_FRAGILE"
    elif any(
        status == "INSUFFICIENT_EVEN_FOR_WEAK_CONSENSUS_IN_ALL_CELLS"
        for status in statuses
    ):
        overall = "AT_LEAST_ONE_TASK_FAILS_WEAK_ALL_CELL_SUPPORT"
    else:
        overall = "LIMITED_OR_WEAK_MECHANISM_SUPPORT"

    result["overall_empirical_status"] = overall
    return result


def markdown_table(rows: Iterable[Iterable[Any]], headers: list[str]) -> list[str]:
    output = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        output.append("| " + " | ".join(str(value) for value in row) + " |")
    return output


def make_report(
    metadata: dict[str, Any],
    aggregate: pd.DataFrame,
    pair_aggregate: pd.DataFrame,
    gates: dict[str, Any],
    capacity: pd.DataFrame,
) -> str:
    lines: list[str] = [
        "# DEJA-VU MM-SAGE-DG Gradient-Support Capacity Audit",
        "",
        f"Generated: `{metadata['generated_at_utc']}`",
        "",
        "This is a data-capacity audit only. No EEG/EMG model and no "
        "MM-SAGE gradient was trained.",
        "",
        "## Frozen inputs",
        "",
        f"- Label manifest: `{metadata['label_manifest']}`",
        f"- Label-manifest SHA-256: `{metadata['label_manifest_sha256']}`",
        f"- Frozen assignments: `{metadata['assignment_file']}`",
        f"- Git branch: `{metadata['git_branch']}`",
        f"- Git HEAD: `{metadata['git_head']}`",
        "- Cohort B: 24 participants, 30 participant-sessions, "
        "90 emotional presentations, 16 exact videos.",
        "- Primary labels: after-only discard midpoint.",
        "- Frozen evaluation: 5 repetitions × 3 subject folds × "
        "3 exact-video folds.",
        "",
        "## Eligibility definitions",
        "",
        "- `weak_1trial`: at least one scored trial for the subject-class.",
        "- `minimal_2trials`: at least two scored trials for the subject-class.",
        "- `strong_2trials_2videos`: at least two scored trials from at least "
        "two exact videos for the subject-class.",
        "- MM-SAGE consensus threshold audited here: at least three eligible "
        "subjects per class.",
        "",
        "## Scenario definitions",
        "",
        "- `outer_source`: final outer-cell source pool, normally 16 subjects "
        "and 10/11 exact videos.",
        "- `inner_subject_only`: one of the two source subject folds is reserved "
        "for validation.",
        "- `inner_video_only`: one of the two source video folds is reserved "
        "for validation.",
        "- `inner_joint`: one source subject fold and one source video fold "
        "remain for fitting; the other source folds form a leakage-safe joint "
        "validation configuration.",
        "",
        "## Aggregate gradient-support capacity",
        "",
    ]

    display = aggregate[
        aggregate["eligibility_level"].isin(
            ["weak_1trial", "minimal_2trials", "strong_2trials_2videos"]
        )
    ].copy()
    rows = []
    for row in display.itertuples():
        rows.append(
            [
                row.scenario_type,
                row.task,
                row.class_name,
                row.eligibility_level,
                row.configuration_count,
                f"{row.eligible_subjects_min}/"
                f"{row.eligible_subjects_median:.1f}/"
                f"{row.eligible_subjects_max}",
                f"{row.M_ge_3_pass_rate:.3f}",
                row.configurations_with_M_lt_3,
                f"{row.scored_class_trials_min}/"
                f"{row.scored_class_trials_median:.1f}",
                row.class_unique_videos_min,
            ]
        )
    lines.extend(
        markdown_table(
            rows,
            [
                "Scenario",
                "Task",
                "Class",
                "Eligibility",
                "Configs",
                "Eligible M min/median/max",
                "M≥3 rate",
                "M<3 configs",
                "Class trials min/median",
                "Min exact videos",
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Same-subject support for both classes",
            "",
            "This is diagnostic. The class-conditional consensus can use "
            "different subject sets, but a very small intersection means that "
            "Low and High gradients are estimated from materially different "
            "subject populations.",
            "",
        ]
    )
    pair_rows = []
    for row in pair_aggregate.itertuples():
        pair_rows.append(
            [
                row.scenario_type,
                row.task,
                row.eligibility_level,
                row.configuration_count,
                f"{row.both_classes_subjects_min}/"
                f"{row.both_classes_subjects_median:.1f}/"
                f"{row.both_classes_subjects_max}",
                f"{row.same_subject_trio_pass_rate:.3f}",
            ]
        )
    lines.extend(
        markdown_table(
            pair_rows,
            [
                "Scenario",
                "Task",
                "Eligibility",
                "Configs",
                "Both-class subjects min/median/max",
                "Same-subject trio rate",
            ],
        )
    )

    lines.extend(["", "## Predeclared empirical gates", ""])
    for task in TASKS:
        task_gate = gates[task]
        lines.append(f"### {task.capitalize()}")
        lines.append("")
        gate_rows = []
        for level_name, _, _ in ELIGIBILITY_LEVELS:
            values = task_gate[level_name]
            gate_rows.append(
                [
                    level_name,
                    values["outer_min_eligible_subjects_any_class"],
                    f"{values['outer_M_ge_3_pass_rate']:.3f}",
                    str(values["outer_all_classes_all_cells_M_ge_3"]),
                    f"{values['inner_joint_M_ge_3_pass_rate']:.3f}",
                    values["outer_same_subject_both_classes_min"],
                    f"{values['outer_same_subject_trio_pass_rate']:.3f}",
                ]
            )
        lines.extend(
            markdown_table(
                gate_rows,
                [
                    "Eligibility",
                    "Outer min M",
                    "Outer M≥3 rate",
                    "All outer cells pass",
                    "Inner-joint M≥3 rate",
                    "Outer min same-subject both classes",
                    "Same-subject trio rate",
                ],
            )
        )
        lines.extend(
            [
                "",
                f"Empirical capacity status: "
                f"**{task_gate['empirical_status']}**",
                "",
            ]
        )

    lines.extend(
        [
            "## Overall empirical status",
            "",
            f"**{gates['overall_empirical_status']}**",
            "",
            "This status is not yet the paper-level verdict. It is the exact "
            "data-support result required before deciding whether the full "
            "MM-SAGE-DG mechanism, a weakened single-trial variant, or only a "
            "secondary stress test is defensible.",
            "",
            "## Important interpretation rules",
            "",
            "1. Windows from one presentation do not create independent trials "
            "or exact-video diversity.",
            "2. `uniform_random_trio_acceptance_probability` assumes subjects "
            "are sampled uniformly from the nominal source pool. A sampler "
            "restricted to eligible subjects avoids resampling, but cannot "
            "create missing subject-class evidence.",
            "3. Different eligible subject sets for Low and High can confound "
            "class comparison with subject composition.",
            "4. `inner_joint` is deliberately strict because leakage-safe "
            "hyperparameter selection must reserve both source subjects and "
            "source videos.",
            "5. Passing this support audit does not prove that real gradients "
            "are stable or emotion-specific. A later pilot must still compare "
            "real-class, shuffled-class, and stimulus-controlled gradient "
            "agreement.",
            "",
            "## Most capacity-limited outer configurations",
            "",
        ]
    )

    strong_outer = capacity[
        (capacity["scenario_type"] == "outer_source")
        & (
            capacity["eligibility_level"]
            == "strong_2trials_2videos"
        )
    ].sort_values(
        ["eligible_subject_count", "scored_class_trials", "class_unique_videos"]
    )
    limited_rows = []
    for row in strong_outer.head(20).itertuples():
        limited_rows.append(
            [
                row.outer_cell,
                row.task,
                row.class_name,
                row.eligible_subject_count,
                row.scored_class_trials,
                row.class_unique_videos,
                row.eligible_subject_ids or "—",
            ]
        )
    lines.extend(
        markdown_table(
            limited_rows,
            [
                "Outer cell",
                "Task",
                "Class",
                "Strong eligible M",
                "Scored class trials",
                "Exact videos",
                "Eligible subjects",
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Outputs",
            "",
            "- `docs/dejavu_mm_sage_gradient_support_by_subject.csv`",
            "- `docs/dejavu_mm_sage_gradient_support_capacity.csv`",
            "- `docs/dejavu_mm_sage_gradient_support_class_pair.csv`",
            "- `docs/dejavu_mm_sage_gradient_support_video_support.csv`",
            "- `docs/dejavu_mm_sage_gradient_support_aggregate.csv`",
            "- `docs/dejavu_mm_sage_gradient_support_pair_aggregate.csv`",
            "- `docs/dejavu_mm_sage_gradient_support_audit.json`",
            "- `docs/dejavu_mm_sage_gradient_support_audit.md`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    docs_dir = repo_root / "docs"
    manifests_dir = repo_root / "manifests"
    folds_dir = repo_root / "folds"

    label_path = manifests_dir / "dejavu_cohort_b_primary_labels.csv"
    assignment_path = folds_dir / "dejavu_joint_cv_repeated_assignments.csv"
    protocol_path = folds_dir / "dejavu_joint_cv_protocol.json"

    for path in (label_path, assignment_path, protocol_path):
        if not path.exists():
            raise AuditError(f"Required frozen artifact is missing: {path}")

    labels = validate_and_prepare_labels(pd.read_csv(label_path))
    assignments = validate_assignments(pd.read_csv(assignment_path))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    if str(protocol.get("status")) != "LOCK_WITH_CAPACITY_CAUTION":
        raise AuditError(
            "Frozen protocol status is not LOCK_WITH_CAPACITY_CAUTION."
        )
    outer = protocol.get("outer_protocol", {})
    if int(outer.get("subject_folds", -1)) != 3:
        raise AuditError("Frozen protocol does not use 3 subject folds.")
    if int(outer.get("video_folds", -1)) != 3:
        raise AuditError("Frozen protocol does not use 3 video folds.")
    if int(outer.get("repetitions", -1)) != 5:
        raise AuditError("Frozen protocol does not use 5 repetitions.")

    all_subject_rows: list[dict[str, Any]] = []
    all_capacity_rows: list[dict[str, Any]] = []
    all_pair_rows: list[dict[str, Any]] = []
    all_video_rows: list[dict[str, Any]] = []

    scenario_count = 0
    for repetition in EXPECTED_REPETITIONS:
        participant_map, video_map = fold_maps(assignments, repetition)

        if set(participant_map) != set(labels["participant_id"].unique()):
            raise AuditError(
                f"Repetition {repetition}: participant assignment set mismatch."
            )
        if set(video_map) != set(labels["video_name"].unique()):
            raise AuditError(
                f"Repetition {repetition}: video assignment set mismatch."
            )

        for held_subject_fold in EXPECTED_SUBJECT_FOLDS:
            for held_video_fold in EXPECTED_VIDEO_FOLDS:
                scenarios = build_scenarios(
                    repetition,
                    held_subject_fold,
                    held_video_fold,
                )
                for scenario in scenarios:
                    (
                        subject_rows,
                        capacity_rows,
                        pair_rows,
                        video_rows,
                    ) = analyse_scenario(
                        labels,
                        scenario,
                        participant_map,
                        video_map,
                    )
                    all_subject_rows.extend(subject_rows)
                    all_capacity_rows.extend(capacity_rows)
                    all_pair_rows.extend(pair_rows)
                    all_video_rows.extend(video_rows)
                    scenario_count += 1

    expected_scenarios = 5 * 9 * 9
    if scenario_count != expected_scenarios:
        raise AuditError(
            f"Expected {expected_scenarios} scenarios, observed {scenario_count}."
        )

    subject_df = pd.DataFrame(all_subject_rows)
    capacity_df = pd.DataFrame(all_capacity_rows)
    pair_df = pd.DataFrame(all_pair_rows)
    video_df = pd.DataFrame(all_video_rows)
    aggregate_df = aggregate_capacity(capacity_df)
    pair_aggregate_df = aggregate_class_pairs(pair_df)
    gates = task_gate_summary(capacity_df, pair_df)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "git_branch": git_value(repo_root, "branch", "--show-current"),
        "git_head": git_value(repo_root, "rev-parse", "HEAD"),
        "git_status_before_output": git_value(repo_root, "status", "--short"),
        "label_manifest": str(label_path),
        "label_manifest_sha256": sha256_file(label_path),
        "assignment_file": str(assignment_path),
        "assignment_file_sha256": sha256_file(assignment_path),
        "protocol_file": str(protocol_path),
        "protocol_file_sha256": sha256_file(protocol_path),
        "scenario_count": scenario_count,
        "outer_source_scenarios": int(
            capacity_df.loc[
                capacity_df["scenario_type"] == "outer_source",
                "scenario_id",
            ].nunique()
        ),
        "inner_subject_only_scenarios": int(
            capacity_df.loc[
                capacity_df["scenario_type"] == "inner_subject_only",
                "scenario_id",
            ].nunique()
        ),
        "inner_video_only_scenarios": int(
            capacity_df.loc[
                capacity_df["scenario_type"] == "inner_video_only",
                "scenario_id",
            ].nunique()
        ),
        "inner_joint_scenarios": int(
            capacity_df.loc[
                capacity_df["scenario_type"] == "inner_joint",
                "scenario_id",
            ].nunique()
        ),
    }

    output_paths = {
        "subject": docs_dir
        / "dejavu_mm_sage_gradient_support_by_subject.csv",
        "capacity": docs_dir
        / "dejavu_mm_sage_gradient_support_capacity.csv",
        "pair": docs_dir
        / "dejavu_mm_sage_gradient_support_class_pair.csv",
        "video": docs_dir
        / "dejavu_mm_sage_gradient_support_video_support.csv",
        "aggregate": docs_dir
        / "dejavu_mm_sage_gradient_support_aggregate.csv",
        "pair_aggregate": docs_dir
        / "dejavu_mm_sage_gradient_support_pair_aggregate.csv",
        "json": docs_dir
        / "dejavu_mm_sage_gradient_support_audit.json",
        "markdown": docs_dir
        / "dejavu_mm_sage_gradient_support_audit.md",
    }

    atomic_write_csv(subject_df, output_paths["subject"], args.overwrite)
    atomic_write_csv(capacity_df, output_paths["capacity"], args.overwrite)
    atomic_write_csv(pair_df, output_paths["pair"], args.overwrite)
    atomic_write_csv(video_df, output_paths["video"], args.overwrite)
    atomic_write_csv(aggregate_df, output_paths["aggregate"], args.overwrite)
    atomic_write_csv(
        pair_aggregate_df,
        output_paths["pair_aggregate"],
        args.overwrite,
    )

    payload = {
        "metadata": metadata,
        "eligibility_levels": [
            {
                "name": name,
                "minimum_trials": min_trials,
                "minimum_exact_videos": min_videos,
            }
            for name, min_trials, min_videos in ELIGIBILITY_LEVELS
        ],
        "minimum_consensus_subjects": MIN_CONSENSUS_SUBJECTS,
        "empirical_gates": gates,
        "aggregate_capacity": aggregate_df.to_dict(orient="records"),
        "aggregate_class_pair_support": pair_aggregate_df.to_dict(
            orient="records"
        ),
        "outputs": {key: str(value) for key, value in output_paths.items()},
    }
    atomic_write_text(
        output_paths["json"],
        json.dumps(json_safe(payload), indent=2, sort_keys=True),
        args.overwrite,
    )
    report = make_report(
        metadata,
        aggregate_df,
        pair_aggregate_df,
        gates,
        capacity_df,
    )
    atomic_write_text(output_paths["markdown"], report, args.overwrite)

    print()
    print("DEJA-VU MM-SAGE-DG GRADIENT-SUPPORT CHECKPOINT")
    print(f"Scenarios audited: {scenario_count}")
    print(
        "Outer source cells: "
        f"{metadata['outer_source_scenarios']}"
    )
    print(
        "Inner joint training configurations: "
        f"{metadata['inner_joint_scenarios']}"
    )
    for task in TASKS:
        task_gate = gates[task]
        strong = task_gate["strong_2trials_2videos"]
        minimal = task_gate["minimal_2trials"]
        weak = task_gate["weak_1trial"]
        print(
            f"{task.upper()} | status={task_gate['empirical_status']} | "
            f"outer strong min M={strong['outer_min_eligible_subjects_any_class']} | "
            f"outer strong M>=3 rate={strong['outer_M_ge_3_pass_rate']:.3f} | "
            f"inner-joint strong M>=3 rate="
            f"{strong['inner_joint_M_ge_3_pass_rate']:.3f} | "
            f"outer minimal M>=3 rate={minimal['outer_M_ge_3_pass_rate']:.3f} | "
            f"outer weak M>=3 rate={weak['outer_M_ge_3_pass_rate']:.3f}"
        )
    print(
        "Overall empirical status: "
        f"{gates['overall_empirical_status']}"
    )
    print(f"Report: {output_paths['markdown']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
