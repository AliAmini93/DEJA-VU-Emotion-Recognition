#!/usr/bin/env python3
"""Run leakage-safe shortcut, order/video-confounding, and null audits.

Scope:
- frozen DEJA-VU Cohort B;
- frozen 3x3 repeated Joint Subject-Stimulus CV;
- repetition 0 primary, repetitions 1-4 sensitivity;
- no EEG, EMG, fusion, or physiological model training.

Legal primary-test baselines:
- global train prior;
- emotional presentation-position train prior;
- quadratic logistic regression using presentation position only.

Diagnostic identity priors:
- source/seen subject x unseen video: train-only subject prior;
- unseen subject x source/seen video: train-only video prior.

Null test:
- primary discard-midpoint policy;
- 250 deterministic permutations per repetition/task/baseline;
- labels, including the missing midpoint state, are permuted within each
  participant-session;
- test labels remain untouched;
- Benjamini-Hochberg FDR correction across all null tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.stats import entropy
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    normalized_mutual_info_score,
    roc_auc_score,
)


EXPECTED_BRANCH = "dejavu-cohort-b-joint-cv-audit"
EXPECTED_HEAD_PREFIX = "719d300"
EXPECTED_MANIFEST_SHA256 = (
    "77f0b77c4c889cd62761bcd0f805a00de33d7803e112ade7055efe0fe8607a70"
)
PRIMARY_POLICY = "discard_midpoint"
TASKS = ("valence", "arousal")
POLICIES = (
    "discard_midpoint",
    "midpoint_as_low",
    "midpoint_as_high",
)
BASELINES = (
    "global_train_prior",
    "position_train_prior",
    "position_quadratic_logistic",
)
NULL_BASELINES = (
    "position_train_prior",
    "position_quadratic_logistic",
)
DEFAULT_PERMUTATIONS = 250


class AuditError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--permutations",
        type=int,
        default=DEFAULT_PERMUTATIONS,
    )
    return parser.parse_args()


def run_git(repo_root: Path, *args: str) -> str:
    import subprocess

    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()


def refuse_overwrite(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        raise AuditError(
            "Refusing to overwrite existing outputs:\n"
            + "\n".join(f"- {path}" for path in existing)
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def seed_from(*parts: object) -> int:
    payload = "|".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % (2**63 - 1)


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    mapping = {
        "true": True,
        "1": True,
        "yes": True,
        "false": False,
        "0": False,
        "no": False,
        "nan": False,
        "none": False,
        "": False,
    }
    normalized = series.astype(str).str.strip().str.lower()
    unknown = sorted(set(normalized.unique()) - set(mapping))
    if unknown:
        raise AuditError(
            f"Unrecognized boolean values in {series.name}: {unknown}"
        )
    return normalized.map(mapping).astype(bool)


def labels_for_policy(
    frame: pd.DataFrame,
    task: str,
    policy: str,
) -> np.ndarray:
    score = pd.to_numeric(frame[f"after_{task}"], errors="coerce").to_numpy(
        dtype=float
    )
    output = np.full(len(score), -1, dtype=int)
    if policy == "discard_midpoint":
        output[score < 5] = 0
        output[score > 5] = 1
    elif policy == "midpoint_as_low":
        output[score <= 5] = 0
        output[score > 5] = 1
    elif policy == "midpoint_as_high":
        output[score < 5] = 0
        output[score >= 5] = 1
    else:
        raise ValueError(policy)
    output[~np.isfinite(score)] = -1
    return output


def position_features(position: np.ndarray) -> np.ndarray:
    numeric = np.asarray(position, dtype=float)
    centered = numeric - 2.0
    return np.column_stack([centered, centered**2])


def probability_to_label(probability: np.ndarray) -> np.ndarray:
    return (np.asarray(probability, dtype=float) >= 0.5).astype(int)


def fit_predict_global(
    train_position: np.ndarray,
    train_labels: np.ndarray,
    test_position: np.ndarray,
) -> np.ndarray:
    del train_position
    valid = train_labels >= 0
    if not valid.any():
        raise AuditError("Global prior received no valid training labels")
    prevalence = float(np.mean(train_labels[valid]))
    return np.full(len(test_position), prevalence, dtype=float)


def fit_predict_position_prior(
    train_position: np.ndarray,
    train_labels: np.ndarray,
    test_position: np.ndarray,
) -> np.ndarray:
    valid = train_labels >= 0
    if not valid.any():
        raise AuditError("Position prior received no valid training labels")
    global_prevalence = float(np.mean(train_labels[valid]))
    mapping: dict[int, float] = {}
    for value in sorted(set(train_position[valid].astype(int).tolist())):
        mask = valid & (train_position.astype(int) == value)
        mapping[int(value)] = float(np.mean(train_labels[mask]))
    return np.asarray(
        [
            mapping.get(int(value), global_prevalence)
            for value in test_position
        ],
        dtype=float,
    )


def fit_predict_quadratic(
    train_position: np.ndarray,
    train_labels: np.ndarray,
    test_position: np.ndarray,
) -> np.ndarray:
    # Some discard-midpoint cells contain zero retained test labels.
    # scikit-learn rejects a zero-row prediction matrix, so return empty.
    if len(test_position) == 0:
        return np.empty(0, dtype=float)

    valid = train_labels >= 0
    if not valid.any():
        raise AuditError("Quadratic baseline received no valid labels")
    y = train_labels[valid]
    if np.unique(y).size < 2:
        return np.full(len(test_position), float(np.mean(y)), dtype=float)

    model = LogisticRegression(
        C=1e6,
        solver="lbfgs",
        max_iter=2000,
        random_state=0,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        model.fit(position_features(train_position[valid]), y)
    return model.predict_proba(position_features(test_position))[:, 1]


BASELINE_FUNCTIONS: dict[
    str,
    Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray],
] = {
    "global_train_prior": fit_predict_global,
    "position_train_prior": fit_predict_position_prior,
    "position_quadratic_logistic": fit_predict_quadratic,
}


def compute_metrics(
    true_labels: np.ndarray,
    probability: np.ndarray,
) -> dict[str, float | int | None]:
    true_labels = np.asarray(true_labels, dtype=int)
    probability = np.asarray(probability, dtype=float)
    if len(true_labels) == 0:
        return {
            "n": 0,
            "low": 0,
            "high": 0,
            "accuracy": None,
            "balanced_accuracy": None,
            "macro_f1": None,
            "roc_auc": None,
            "brier": None,
        }

    predicted = probability_to_label(probability)
    both_classes = np.unique(true_labels).size == 2
    return {
        "n": int(len(true_labels)),
        "low": int((true_labels == 0).sum()),
        "high": int((true_labels == 1).sum()),
        "accuracy": float(accuracy_score(true_labels, predicted)),
        "balanced_accuracy": (
            float(balanced_accuracy_score(true_labels, predicted))
            if both_classes
            else None
        ),
        "macro_f1": (
            float(f1_score(true_labels, predicted, average="macro"))
            if both_classes
            else None
        ),
        "roc_auc": (
            float(roc_auc_score(true_labels, probability))
            if both_classes
            else None
        ),
        "brier": float(brier_score_loss(true_labels, probability)),
    }


def bh_fdr(p_values: list[float]) -> list[float]:
    p = np.asarray(p_values, dtype=float)
    order = np.argsort(p)
    ranked = p[order]
    adjusted = np.empty_like(ranked)
    running = 1.0
    m = len(p)
    for index in range(m - 1, -1, -1):
        rank = index + 1
        value = min(running, ranked[index] * m / rank)
        adjusted[index] = value
        running = value
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result.tolist()


def normalize_position(frame: pd.DataFrame) -> pd.Series:
    candidates = (
        "chronological_position",
        "presentation_order",
        "position",
    )
    column = next(
        (candidate for candidate in candidates if candidate in frame.columns),
        None,
    )
    if column is None:
        raise AuditError(
            "No chronological-position column exists in the label manifest"
        )

    numeric = pd.to_numeric(frame[column], errors="coerce")
    if numeric.isna().any():
        raise AuditError(f"Invalid values in position column {column}")

    working = frame[
        ["participant_session_key"]
    ].copy()
    working["_position"] = numeric
    working["_row_index"] = np.arange(len(frame))
    working = working.sort_values(
        ["participant_session_key", "_position", "_row_index"]
    )
    working["emotional_position"] = (
        working.groupby("participant_session_key").cumcount() + 1
    )
    restored = (
        working.sort_values("_row_index")["emotional_position"]
        .reset_index(drop=True)
        .astype(int)
    )
    if not restored.between(1, 3).all():
        raise AuditError("Emotional positions are not restricted to 1..3")
    session_counts = restored.groupby(
        frame["participant_session_key"].reset_index(drop=True)
    ).size()
    if not session_counts.eq(3).all():
        raise AuditError(
            "Every retained participant-session must have 3 emotional rows"
        )
    return restored


def build_fold_maps(
    assignments: pd.DataFrame,
    repetition: int,
) -> tuple[dict[str, int], dict[str, int]]:
    subset = assignments[assignments["repetition"] == repetition]
    participant_map = {
        str(row["entity_id"]): int(row["fold"])
        for _, row in subset[
            subset["entity_type"] == "participant"
        ].iterrows()
    }
    video_map = {
        str(row["entity_id"]): int(row["fold"])
        for _, row in subset[
            subset["entity_type"] == "video"
        ].iterrows()
    }
    if len(participant_map) != 24 or len(video_map) != 16:
        raise AuditError(
            f"Invalid assignments for repetition {repetition}: "
            f"participants={len(participant_map)}, videos={len(video_map)}"
        )
    return participant_map, video_map


def pooled_primary_baseline(
    frame: pd.DataFrame,
    target: np.ndarray,
    participant_map: dict[str, int],
    video_map: dict[str, int],
    baseline: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    position = frame["emotional_position"].to_numpy(dtype=int)
    participant_fold = (
        frame["participant_id"].astype(str).map(participant_map).to_numpy()
    )
    video_fold = frame["video_name"].astype(str).map(video_map).to_numpy()
    if pd.isna(participant_fold).any() or pd.isna(video_fold).any():
        raise AuditError("Incomplete fold mapping")

    pooled_true: list[int] = []
    pooled_probability: list[float] = []
    cell_rows: list[dict[str, Any]] = []
    predictor = BASELINE_FUNCTIONS[baseline]

    for subject_fold in (1, 2, 3):
        subject_held = participant_fold == subject_fold
        for content_fold in (1, 2, 3):
            content_held = video_fold == content_fold
            train_mask = (~subject_held) & (~content_held)
            test_mask = subject_held & content_held
            valid_test = test_mask & (target >= 0)

            probability = predictor(
                position[train_mask],
                target[train_mask],
                position[valid_test],
            )
            true = target[valid_test]
            pooled_true.extend(true.tolist())
            pooled_probability.extend(probability.tolist())

            metrics = compute_metrics(true, probability)
            cell_rows.append(
                {
                    "cell_id": f"S{subject_fold}_V{content_fold}",
                    "subject_fold": subject_fold,
                    "video_fold": content_fold,
                    "raw_test_rows": int(test_mask.sum()),
                    **metrics,
                }
            )

    summary = compute_metrics(
        np.asarray(pooled_true, dtype=int),
        np.asarray(pooled_probability, dtype=float),
    )
    return summary, cell_rows


def identity_diagnostic(
    frame: pd.DataFrame,
    target: np.ndarray,
    participant_map: dict[str, int],
    video_map: dict[str, int],
    identity: str,
) -> dict[str, Any]:
    # Diagnostic regions overlap across Cartesian cells. Compute each
    # cell separately and macro-average defined metrics instead of pooling
    # duplicated rows as if they were independent.
    participant_fold = (
        frame["participant_id"].astype(str).map(participant_map).to_numpy()
    )
    video_fold = frame["video_name"].astype(str).map(video_map).to_numpy()

    cell_metrics: list[dict[str, Any]] = []
    unique_row_indices: set[int] = set()
    evaluation_instances = 0
    covered_instances = 0

    for subject_fold in (1, 2, 3):
        subject_held = participant_fold == subject_fold
        for content_fold in (1, 2, 3):
            content_held = video_fold == content_fold
            train_mask = (~subject_held) & (~content_held)

            if identity == "subject":
                diagnostic_mask = (~subject_held) & content_held
                identity_values = frame["participant_id"].astype(str).to_numpy()
            elif identity == "video":
                diagnostic_mask = subject_held & (~content_held)
                identity_values = frame["video_name"].astype(str).to_numpy()
            else:
                raise ValueError(identity)

            valid_train = train_mask & (target >= 0)
            valid_test = diagnostic_mask & (target >= 0)
            test_indices = np.flatnonzero(valid_test)
            if test_indices.size == 0:
                continue

            global_prevalence = float(np.mean(target[valid_train]))
            mapping: dict[str, float] = {}
            train_identity = identity_values[valid_train]
            train_target = target[valid_train]
            for value in sorted(set(train_identity.tolist())):
                mask = train_identity == value
                mapping[str(value)] = float(np.mean(train_target[mask]))

            test_identity = identity_values[valid_test]
            covered = np.asarray(
                [str(value) in mapping for value in test_identity],
                dtype=bool,
            )
            probability = np.asarray(
                [
                    mapping.get(str(value), global_prevalence)
                    for value in test_identity
                ],
                dtype=float,
            )
            metrics = compute_metrics(target[valid_test], probability)
            cell_metrics.append(metrics)

            unique_row_indices.update(test_indices.tolist())
            evaluation_instances += int(test_indices.size)
            covered_instances += int(covered.sum())

    if not cell_metrics:
        raise AuditError(
            f"No evaluable diagnostic cells for identity={identity}"
        )

    def macro_metric(name: str) -> float | None:
        values = [
            float(row[name])
            for row in cell_metrics
            if row.get(name) is not None
        ]
        return float(np.mean(values)) if values else None

    return {
        "n": evaluation_instances,
        "n_unique": int(len(unique_row_indices)),
        "cells_evaluated": int(len(cell_metrics)),
        "identity_prior_coverage": (
            float(covered_instances / evaluation_instances)
            if evaluation_instances
            else None
        ),
        "low": int(sum(int(row["low"]) for row in cell_metrics)),
        "high": int(sum(int(row["high"]) for row in cell_metrics)),
        "accuracy": macro_metric("accuracy"),
        "balanced_accuracy": macro_metric("balanced_accuracy"),
        "macro_f1": macro_metric("macro_f1"),
        "roc_auc": macro_metric("roc_auc"),
        "brier": macro_metric("brier"),
    }


def permute_within_session(
    target: np.ndarray,
    session_values: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    permuted = target.copy()
    for session in sorted(set(session_values.tolist())):
        indices = np.flatnonzero(session_values == session)
        permuted[indices] = rng.permutation(permuted[indices])
    return permuted


def concentration_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_positions = int(frame["emotional_position"].nunique())
    for video, subset in frame.groupby("video_name", dropna=False):
        counts = (
            subset["emotional_position"]
            .value_counts()
            .sort_index()
        )
        probabilities = counts.to_numpy(dtype=float) / counts.sum()
        normalized_entropy = (
            float(entropy(probabilities) / math.log(total_positions))
            if len(probabilities) > 1
            else 0.0
        )
        modal_position = int(counts.idxmax())
        rows.append(
            {
                "video_name": video,
                "presentations": int(len(subset)),
                "participants": int(subset["participant_id"].nunique()),
                "participant_sessions": int(
                    subset["participant_session_key"].nunique()
                ),
                "unique_positions": int(
                    subset["emotional_position"].nunique()
                ),
                "modal_position": modal_position,
                "modal_position_fraction": float(
                    counts.max() / counts.sum()
                ),
                "normalized_position_entropy": normalized_entropy,
                "position_1_count": int(counts.get(1, 0)),
                "position_2_count": int(counts.get(2, 0)),
                "position_3_count": int(counts.get(3, 0)),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["modal_position_fraction", "presentations", "video_name"],
        ascending=[False, True, True],
    )


def main() -> int:
    args = parse_args()
    if args.permutations < 100:
        raise AuditError("--permutations must be at least 100")

    repo_root = args.repo_root.resolve()
    docs_dir = repo_root / "docs"
    folds_dir = repo_root / "folds"
    manifests_dir = repo_root / "manifests"

    branch = run_git(repo_root, "branch", "--show-current")
    head = run_git(repo_root, "rev-parse", "--short", "HEAD")
    status = run_git(repo_root, "status", "--short")
    if branch != EXPECTED_BRANCH:
        raise AuditError(
            f"Expected branch {EXPECTED_BRANCH}, found {branch}"
        )
    if not head.startswith(EXPECTED_HEAD_PREFIX):
        raise AuditError(
            f"Expected HEAD prefix {EXPECTED_HEAD_PREFIX}, found {head}"
        )
    if status:
        raise AuditError(
            "Working tree must be clean before shortcut audit:\n" + status
        )

    labels_path = manifests_dir / "dejavu_cohort_b_primary_labels.csv"
    assignments_path = (
        folds_dir / "dejavu_joint_cv_repeated_assignments.csv"
    )
    protocol_path = folds_dir / "dejavu_joint_cv_protocol.json"

    for path in (labels_path, assignments_path, protocol_path):
        if not path.exists():
            raise AuditError(f"Required frozen artifact missing: {path}")

    output_paths = [
        docs_dir / "dejavu_shortcut_baseline_cell_metrics.csv",
        docs_dir / "dejavu_shortcut_baseline_summary.csv",
        docs_dir / "dejavu_shortcut_null_tests.csv",
        docs_dir / "dejavu_order_video_concentration.csv",
        docs_dir / "dejavu_position_label_prevalence.csv",
        docs_dir / "dejavu_shortcut_and_null_audit.json",
        docs_dir / "dejavu_shortcut_and_null_audit.md",
    ]
    refuse_overwrite(output_paths)

    frame = pd.read_csv(labels_path)
    assignments = pd.read_csv(assignments_path)
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))

    source_manifest = Path(protocol["source_manifest"])
    if not source_manifest.exists():
        raise AuditError(
            f"Protocol source manifest no longer exists: {source_manifest}"
        )
    actual_hash = sha256_file(source_manifest)
    if actual_hash != EXPECTED_MANIFEST_SHA256:
        raise AuditError(
            "Frozen source-manifest hash changed: "
            f"{actual_hash}"
        )

    if len(frame) != 90:
        raise AuditError(f"Expected 90 emotional rows, found {len(frame)}")
    frame["emotional_position"] = normalize_position(frame)

    labels = {
        (task, policy): labels_for_policy(frame, task, policy)
        for task in TASKS
        for policy in POLICIES
    }

    # Confounding structure.
    sequence_rows: list[dict[str, Any]] = []
    for session, subset in frame.groupby(
        "participant_session_key",
        dropna=False,
    ):
        ordered = subset.sort_values("emotional_position")
        sequence_rows.append(
            {
                "participant_session_key": session,
                "participant_id": str(
                    ordered["participant_id"].iloc[0]
                ),
                "session_id": str(ordered["session_id"].iloc[0]),
                "video_sequence": " -> ".join(
                    ordered["video_name"].astype(str).tolist()
                ),
            }
        )
    sequence_df = pd.DataFrame(sequence_rows)
    unique_sequences = int(sequence_df["video_sequence"].nunique())
    largest_sequence_group = int(
        sequence_df["video_sequence"].value_counts().max()
    )

    video_codes = pd.Categorical(frame["video_name"].astype(str)).codes
    position_codes = frame["emotional_position"].to_numpy(dtype=int)
    video_position_nmi = float(
        normalized_mutual_info_score(video_codes, position_codes)
    )
    concentration_df = concentration_table(frame)

    prevalence_rows: list[dict[str, Any]] = []
    for task in TASKS:
        for policy in POLICIES:
            target = labels[(task, policy)]
            for position in (1, 2, 3):
                mask = (
                    frame["emotional_position"].to_numpy(dtype=int)
                    == position
                ) & (target >= 0)
                prevalence_rows.append(
                    {
                        "task": task,
                        "policy": policy,
                        "emotional_position": position,
                        "retained": int(mask.sum()),
                        "low": int((target[mask] == 0).sum()),
                        "high": int((target[mask] == 1).sum()),
                        "high_prevalence": (
                            float(np.mean(target[mask]))
                            if mask.any()
                            else None
                        ),
                        "mean_score": float(
                            frame.loc[mask, f"after_{task}"].mean()
                        )
                        if mask.any()
                        else None,
                    }
                )
    prevalence_df = pd.DataFrame(prevalence_rows)

    summary_rows: list[dict[str, Any]] = []
    cell_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []

    for repetition in range(5):
        participant_map, video_map = build_fold_maps(
            assignments,
            repetition,
        )
        role = "primary" if repetition == 0 else "sensitivity"

        for task in TASKS:
            for policy in POLICIES:
                target = labels[(task, policy)]
                for baseline in BASELINES:
                    summary, cells = pooled_primary_baseline(
                        frame,
                        target,
                        participant_map,
                        video_map,
                        baseline,
                    )
                    summary_rows.append(
                        {
                            "repetition": repetition,
                            "role": role,
                            "region": "joint_primary",
                            "task": task,
                            "policy": policy,
                            "baseline": baseline,
                            **summary,
                        }
                    )
                    for cell in cells:
                        cell_rows.append(
                            {
                                "repetition": repetition,
                                "role": role,
                                "region": "joint_primary",
                                "task": task,
                                "policy": policy,
                                "baseline": baseline,
                                **cell,
                            }
                        )

                if policy == PRIMARY_POLICY:
                    for identity, region, name in (
                        (
                            "subject",
                            "seen_subject_unseen_video",
                            "subject_train_prior",
                        ),
                        (
                            "video",
                            "unseen_subject_seen_video",
                            "video_train_prior",
                        ),
                    ):
                        metrics = identity_diagnostic(
                            frame,
                            target,
                            participant_map,
                            video_map,
                            identity,
                        )
                        diagnostic_rows.append(
                            {
                                "repetition": repetition,
                                "role": role,
                                "region": region,
                                "task": task,
                                "policy": policy,
                                "baseline": name,
                                **metrics,
                            }
                        )

    summary_df = pd.DataFrame(summary_rows)
    diagnostics_df = pd.DataFrame(diagnostic_rows)
    combined_summary_df = pd.concat(
        [summary_df, diagnostics_df],
        ignore_index=True,
        sort=False,
    )
    cell_df = pd.DataFrame(cell_rows)

    # Null tests on the two order-aware legal baselines.
    session_values = (
        frame["participant_session_key"].astype(str).to_numpy()
    )
    null_rows: list[dict[str, Any]] = []
    total_jobs = 5 * len(TASKS) * len(NULL_BASELINES)
    completed_jobs = 0

    for repetition in range(5):
        participant_map, video_map = build_fold_maps(
            assignments,
            repetition,
        )
        role = "primary" if repetition == 0 else "sensitivity"

        for task in TASKS:
            true_target = labels[(task, PRIMARY_POLICY)]
            for baseline in NULL_BASELINES:
                observed_row = summary_df[
                    (summary_df["repetition"] == repetition)
                    & (summary_df["task"] == task)
                    & (summary_df["policy"] == PRIMARY_POLICY)
                    & (summary_df["baseline"] == baseline)
                ]
                if len(observed_row) != 1:
                    raise AuditError(
                        "Could not resolve observed shortcut metric"
                    )
                observed_ba = float(
                    observed_row["balanced_accuracy"].iloc[0]
                )

                null_values: list[float] = []
                for permutation in range(args.permutations):
                    rng = np.random.default_rng(
                        seed_from(
                            EXPECTED_MANIFEST_SHA256,
                            repetition,
                            task,
                            baseline,
                            permutation,
                        )
                    )
                    permuted = permute_within_session(
                        true_target,
                        session_values,
                        rng,
                    )
                    # Evaluate permuted-label training only against untouched test labels below.

                    # Predictions were evaluated against permuted labels above.
                    # Recompute predictions trained on permuted labels but
                    # evaluated against untouched true test labels.
                    position = frame["emotional_position"].to_numpy(
                        dtype=int
                    )
                    participant_fold = (
                        frame["participant_id"]
                        .astype(str)
                        .map(participant_map)
                        .to_numpy()
                    )
                    video_fold = (
                        frame["video_name"]
                        .astype(str)
                        .map(video_map)
                        .to_numpy()
                    )
                    pooled_true: list[int] = []
                    pooled_probability: list[float] = []
                    predictor = BASELINE_FUNCTIONS[baseline]

                    for subject_fold in (1, 2, 3):
                        subject_held = participant_fold == subject_fold
                        for video_fold_id in (1, 2, 3):
                            video_held = video_fold == video_fold_id
                            train_mask = (~subject_held) & (~video_held)
                            test_mask = (
                                subject_held
                                & video_held
                                & (true_target >= 0)
                            )
                            probability = predictor(
                                position[train_mask],
                                permuted[train_mask],
                                position[test_mask],
                            )
                            pooled_true.extend(
                                true_target[test_mask].tolist()
                            )
                            pooled_probability.extend(
                                probability.tolist()
                            )

                    true_array = np.asarray(pooled_true, dtype=int)
                    probability_array = np.asarray(
                        pooled_probability,
                        dtype=float,
                    )
                    predicted = probability_to_label(
                        probability_array
                    )
                    null_ba = float(
                        balanced_accuracy_score(
                            true_array,
                            predicted,
                        )
                    )
                    null_values.append(null_ba)

                null_array = np.asarray(null_values, dtype=float)
                p_value = float(
                    (1 + np.sum(null_array >= observed_ba))
                    / (len(null_array) + 1)
                )
                null_rows.append(
                    {
                        "repetition": repetition,
                        "role": role,
                        "task": task,
                        "policy": PRIMARY_POLICY,
                        "baseline": baseline,
                        "permutations": args.permutations,
                        "observed_balanced_accuracy": observed_ba,
                        "null_mean": float(null_array.mean()),
                        "null_median": float(
                            np.median(null_array)
                        ),
                        "null_p05": float(
                            np.quantile(null_array, 0.05)
                        ),
                        "null_p95": float(
                            np.quantile(null_array, 0.95)
                        ),
                        "effect_vs_null_median": float(
                            observed_ba - np.median(null_array)
                        ),
                        "p_value_one_sided": p_value,
                    }
                )
                completed_jobs += 1
                print(
                    f"Null {completed_jobs}/{total_jobs}: "
                    f"rep{repetition:02d} {task} {baseline} "
                    f"observed={observed_ba:.4f}, "
                    f"null_median={np.median(null_array):.4f}, "
                    f"p={p_value:.6f}"
                )

    null_df = pd.DataFrame(null_rows)
    null_df["fdr_q"] = bh_fdr(
        null_df["p_value_one_sided"].astype(float).tolist()
    )
    null_df["significant_fdr_0_05"] = null_df["fdr_q"] <= 0.05

    # Determine primary legal shortcut gates.
    primary_main = summary_df[
        (summary_df["repetition"] == 0)
        & (summary_df["policy"] == PRIMARY_POLICY)
    ].copy()
    shortcut_gates: dict[str, dict[str, Any]] = {}
    for task in TASKS:
        task_rows = primary_main[primary_main["task"] == task].copy()
        task_rows = task_rows.sort_values(
            ["balanced_accuracy", "baseline"],
            ascending=[False, True],
        )
        best = task_rows.iloc[0]
        empirical_ba = float(best["balanced_accuracy"])
        mandatory_ba_gate = max(0.5, empirical_ba)
        shortcut_gates[task] = {
            "empirical_best_baseline": str(best["baseline"]),
            "empirical_balanced_accuracy": empirical_ba,
            "mandatory_balanced_accuracy_gate": mandatory_ba_gate,
            "gate_source": (
                "empirical_legal_baseline"
                if empirical_ba >= 0.5
                else "theoretical_balanced_accuracy_chance"
            ),
            "accuracy": float(best["accuracy"]),
            "macro_f1": float(best["macro_f1"]),
            "roc_auc": float(best["roc_auc"]),
            "n": int(best["n"]),
        }

    order_material = bool(
        null_df[
            (null_df["repetition"] == 0)
            & (null_df["baseline"] == "position_quadratic_logistic")
        ]["significant_fdr_0_05"].all()
    )
    if order_material:
        decision = "PROCEED_WITH_MATERIAL_POSITION_SHORTCUT_GATE"
    else:
        decision = "PROCEED_WITH_STANDARD_SHORTCUT_GATE"

    concentration_path = output_paths[3]
    prevalence_path = output_paths[4]
    cell_path = output_paths[0]
    summary_path = output_paths[1]
    null_path = output_paths[2]
    json_path = output_paths[5]
    report_path = output_paths[6]

    concentration_df.to_csv(concentration_path, index=False)
    prevalence_df.to_csv(prevalence_path, index=False)
    cell_df.to_csv(cell_path, index=False)
    combined_summary_df.to_csv(summary_path, index=False)
    null_df.to_csv(null_path, index=False)

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": branch,
        "head": head,
        "frozen_manifest_sha256": actual_hash,
        "protocol_status": protocol["status"],
        "cohort": protocol["cohort"],
        "permutations": args.permutations,
        "sequence_structure": {
            "participant_sessions": int(
                frame["participant_session_key"].nunique()
            ),
            "unique_complete_emotional_video_sequences": unique_sequences,
            "largest_identical_sequence_group": largest_sequence_group,
            "nmi_video_vs_emotional_position": video_position_nmi,
            "median_video_unique_positions": float(
                concentration_df["unique_positions"].median()
            ),
            "median_video_modal_position_fraction": float(
                concentration_df[
                    "modal_position_fraction"
                ].median()
            ),
            "median_video_position_entropy": float(
                concentration_df[
                    "normalized_position_entropy"
                ].median()
            ),
        },
        "primary_shortcut_gates": shortcut_gates,
        "decision": decision,
        "order_position_shortcut_material": order_material,
        "legal_primary_test_baselines": list(BASELINES),
        "diagnostic_only_priors": [
            "subject_train_prior on seen-subject x unseen-video",
            "video_train_prior on unseen-subject x seen-video",
        ],
        "forbidden_primary_test_priors": [
            "held-out subject identity prior",
            "held-out video identity prior",
            "canonical quadrant",
            "emotion name",
            "transition identity containing held-out video information",
        ],
        "outputs": [str(path) for path in output_paths],
    }
    json_path.write_text(
        json.dumps(json_safe(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    lines = [
        "# DEJA-VU Frozen Joint-CV Shortcut and Null Audit",
        "",
        f"Generated: `{payload['generated_at_utc']}`",
        "",
        "No EEG, EMG, fusion, or physiological model was trained.",
        "",
        "## Frozen evaluation scope",
        "",
        "- Cohort B: 24 participants, 30 participant-sessions, "
        "90 emotional presentations, 16 exact videos.",
        "- Frozen 3×3 Joint Subject-Stimulus CV.",
        "- Repetition 0 is primary; repetitions 1–4 are sensitivity.",
        "- Primary labels use post-stimulus discard-midpoint policy.",
        "- Predictions are pooled across all nine joint cells before "
        "headline metrics are calculated.",
        "",
        "## Video/order structure",
        "",
        f"- Complete retained emotional sequences: `{len(sequence_df)}`",
        f"- Unique three-video sequences: `{unique_sequences}`",
        f"- Largest identical-sequence group: `{largest_sequence_group}`",
        f"- NMI(video, emotional presentation position): "
        f"`{video_position_nmi:.4f}`",
        f"- Median unique positions per video: "
        f"`{concentration_df['unique_positions'].median():.2f}`",
        f"- Median modal-position fraction per video: "
        f"`{concentration_df['modal_position_fraction'].median():.4f}`",
        "",
        "Unlike a perfect one-sequence dataset, position is not assumed to "
        "equal video identity. The measured association above determines "
        "how serious the legal position shortcut is.",
        "",
        "## Primary repetition: legal joint-test baselines",
        "",
        "| Task | Policy | Baseline | N | Accuracy | Balanced accuracy | "
        "Macro-F1 | ROC-AUC | Brier |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in primary_main.sort_values(
        ["task", "baseline"]
    ).iterrows():
        lines.append(
            f"| {row['task']} | {row['policy']} | {row['baseline']} | "
            f"{int(row['n'])} | {row['accuracy']:.4f} | "
            f"{row['balanced_accuracy']:.4f} | "
            f"{row['macro_f1']:.4f} | "
            f"{row['roc_auc']:.4f} | {row['brier']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Primary shortcut gates for future physiological models",
            "",
            "| Task | Best empirical legal baseline | Empirical BA | "
            "Mandatory BA gate | Gate source | Macro-F1 | ROC-AUC |",
            "|---|---|---:|---:|---|---:|---:|",
        ]
    )
    for task in TASKS:
        gate = shortcut_gates[task]
        lines.append(
            f"| {task} | {gate['empirical_best_baseline']} | "
            f"{gate['empirical_balanced_accuracy']:.4f} | "
            f"{gate['mandatory_balanced_accuracy_gate']:.4f} | "
            f"{gate['gate_source']} | "
            f"{gate['macro_f1']:.4f} | "
            f"{gate['roc_auc']:.4f} |"
        )

    lines.extend(
        [
            "",
            "A future EEG, EMG, or fusion model must be compared against "
            "the corresponding empirical legal shortcut and must also exceed "
            "the theoretical 0.5 balanced-accuracy chance level. The mandatory "
            "BA gate is max(0.5, best empirical legal-baseline BA).",
            "",
            "## Primary repetition: diagnostic identity priors",
            "",
            "| Task | Region | Baseline | Cell-evaluation N | Balanced accuracy | "
            "Macro-F1 | ROC-AUC |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    primary_diagnostics = diagnostics_df[
        diagnostics_df["repetition"] == 0
    ].sort_values(["task", "region"])
    for _, row in primary_diagnostics.iterrows():
        lines.append(
            f"| {row['task']} | {row['region']} | "
            f"{row['baseline']} | {int(row['n'])} | "
            f"{row['balanced_accuracy']:.4f} | "
            f"{row['macro_f1']:.4f} | "
            f"{row['roc_auc']:.4f} |"
        )

    lines.extend(
        [
            "",
            "These identity priors are diagnostic only. Their regions overlap "
            "across Cartesian cells, so scores are macro averages of defined "
            "cell metrics rather than a falsely independent pooled set. Subject "
            "identity and video identity are both unseen in the primary joint test.",
            "",
            "## Position-shortcut null tests",
            "",
            "Training labels, including the missing midpoint state, were "
            "permuted within each participant-session. Test labels were never "
            "permuted. FDR correction covers all repetition × task × shortcut "
            "tests.",
            "",
            "| Rep | Role | Task | Baseline | Observed BA | Null median | "
            "Effect | p | FDR q | Significant |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for _, row in null_df.iterrows():
        lines.append(
            f"| {int(row['repetition'])} | {row['role']} | "
            f"{row['task']} | {row['baseline']} | "
            f"{row['observed_balanced_accuracy']:.4f} | "
            f"{row['null_median']:.4f} | "
            f"{row['effect_vs_null_median']:.4f} | "
            f"{row['p_value_one_sided']:.6f} | "
            f"{row['fdr_q']:.6f} | "
            f"{bool(row['significant_fdr_0_05'])} |"
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"**{decision}**",
            "",
            "Mandatory rules:",
            "",
            "1. Do not provide participant identity, exact video identity, "
            "canonical quadrant, emotion name, or held-out transition identity "
            "as physiological-model inputs.",
            "2. Report improvement over the best legal primary-test shortcut.",
            "3. Keep repetitions 1–4 for sensitivity only; do not tune on them.",
            "4. Use dependence-aware uncertainty over participants/videos and "
            "paired comparisons against the shortcut baseline.",
            "5. Preserve one-presentation and one-class cells in the pooled "
            "repetition; never score them as standalone headline metric units.",
            "",
            "## Outputs",
            "",
        ]
    )
    for path in output_paths:
        lines.append(f"- `{path.relative_to(repo_root)}`")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nDEJA-VU SHORTCUT AND NULL CHECKPOINT")
    print(f"Unique emotional sequences: {unique_sequences}")
    print(f"NMI(video, position): {video_position_nmi:.4f}")
    for task in TASKS:
        gate = shortcut_gates[task]
        print(
            f"Primary {task}: empirical={gate['empirical_best_baseline']} "
            f"BA={gate['empirical_balanced_accuracy']:.4f}; "
            f"mandatory_gate={gate['mandatory_balanced_accuracy_gate']:.4f}"
        )
    print(f"Decision: {decision}")
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
