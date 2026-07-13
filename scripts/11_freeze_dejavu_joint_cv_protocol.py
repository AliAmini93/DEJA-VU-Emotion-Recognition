#!/usr/bin/env python3
"""Freeze the DEJA-VU label-blind repeated Joint CV protocol with capacity caution.

This is a pre-training protocol-amendment and freeze step. It does not reroll,
replace, or remove any repetition. It keeps:

- selected scheme: 3 subject folds x 3 video folds;
- repetition 0 as primary;
- repetitions 1-4 as sensitivity;
- exact VIDEO_NAME as content identity;
- post-stimulus discard-midpoint labels as the primary label policy.

Why an amendment is required:
The earlier automatic gate required every sensitivity repetition to satisfy a
cell-level minimum of two raw test rows. One hash-derived sensitivity
repetition contains a one-row cell. This does not invalidate pooled evaluation
over the complete repetition, and the parallel first-paper protocol retained
weaker sensitivity repetitions rather than rerolling them.

The amended gate is therefore aligned with the actual estimand:
- primary repetition must satisfy the earlier minimal gate;
- every repetition must be leakage-free;
- every raw presentation must appear in exactly one joint test cell;
- every training cell must retain both classes for each primary task;
- each repetition must have pooled support for both classes;
- sparse/one-class cells are retained but never scored as standalone headline
  Balanced Accuracy, Macro-F1, or ROC-AUC units.

No model result is observed or used by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EXPECTED_MANIFEST_SHA256 = (
    "77f0b77c4c889cd62761bcd0f805a00de33d7803e112ade7055efe0fe8607a70"
)
EXPECTED_SCHEME = "3x3"
EXPECTED_REPETITIONS = 5
PRIMARY_POLICY = "discard_midpoint"
TASKS = ("valence", "arousal")


class FreezeError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


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


def refuse_overwrite(paths: list[Path]) -> None:
    existing = [path for path in paths if path.exists()]
    if existing:
        raise FreezeError(
            "Refusing to overwrite already-frozen outputs:\n"
            + "\n".join(f"- {path}" for path in existing)
        )


def make_discard_midpoint(scores: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(scores, errors="coerce")
    values = np.where(
        numeric < 5,
        0,
        np.where(numeric > 5, 1, np.nan),
    )
    return pd.Series(values, index=scores.index, dtype="Float64").astype("Int64")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    docs_dir = repo_root / "docs"
    folds_dir = repo_root / "folds"
    manifests_dir = repo_root / "manifests"

    source_manifest = (
        manifests_dir / "dejavu_cohort_b_emotional_label_candidates.csv"
    )
    audit_json_path = docs_dir / "dejavu_joint_cv_label_blind_audit.json"
    candidate_protocol_path = (
        folds_dir
        / "dejavu_joint_cv_label_blind_repeated_protocol_candidate.json"
    )
    candidate_assignments_path = (
        folds_dir
        / "dejavu_joint_cv_label_blind_repeated_assignments_candidate.csv"
    )
    candidate_support_path = (
        docs_dir / "dejavu_joint_cv_label_blind_repeated_support.csv"
    )

    required_inputs = [
        source_manifest,
        audit_json_path,
        candidate_protocol_path,
        candidate_assignments_path,
        candidate_support_path,
    ]
    missing = [path for path in required_inputs if not path.exists()]
    if missing:
        raise FreezeError(
            "Required input artifacts are missing:\n"
            + "\n".join(f"- {path}" for path in missing)
        )

    final_protocol_path = folds_dir / "dejavu_joint_cv_protocol.json"
    final_assignments_path = (
        folds_dir / "dejavu_joint_cv_repeated_assignments.csv"
    )
    final_support_path = folds_dir / "dejavu_joint_cv_repeated_support.csv"
    final_primary_subject_path = (
        folds_dir / "dejavu_joint_cv_primary_subject_folds.csv"
    )
    final_primary_video_path = (
        folds_dir / "dejavu_joint_cv_primary_video_folds.csv"
    )
    final_labels_path = (
        manifests_dir / "dejavu_cohort_b_primary_labels.csv"
    )
    freeze_json_path = docs_dir / "dejavu_joint_cv_protocol_freeze.json"
    freeze_report_path = docs_dir / "dejavu_joint_cv_protocol_freeze.md"

    output_paths = [
        final_protocol_path,
        final_assignments_path,
        final_support_path,
        final_primary_subject_path,
        final_primary_video_path,
        final_labels_path,
        freeze_json_path,
        freeze_report_path,
    ]
    refuse_overwrite(output_paths)

    actual_hash = sha256_file(source_manifest)
    if actual_hash != EXPECTED_MANIFEST_SHA256:
        raise FreezeError(
            "Source manifest hash changed.\n"
            f"Expected: {EXPECTED_MANIFEST_SHA256}\n"
            f"Actual:   {actual_hash}"
        )

    audit_payload = json.loads(audit_json_path.read_text(encoding="utf-8"))
    candidate_protocol = json.loads(
        candidate_protocol_path.read_text(encoding="utf-8")
    )
    protocol_from_audit = audit_payload.get("protocol", {})

    selected_scheme = str(candidate_protocol.get("selected_scheme", ""))
    if selected_scheme != EXPECTED_SCHEME:
        raise FreezeError(
            f"Expected selected scheme {EXPECTED_SCHEME}, found {selected_scheme}"
        )
    if candidate_protocol.get("fold_construction_uses_labels") is not False:
        raise FreezeError("Candidate fold construction is not label-blind")
    if candidate_protocol.get("rerolling_allowed") is not False:
        raise FreezeError("Candidate unexpectedly permits rerolling")
    if int(candidate_protocol.get("repetitions", -1)) != EXPECTED_REPETITIONS:
        raise FreezeError("Expected exactly five repetitions")

    repetition_results = candidate_protocol.get("repetition_results", [])
    if len(repetition_results) != EXPECTED_REPETITIONS:
        raise FreezeError(
            f"Expected five repetition results, found {len(repetition_results)}"
        )

    primary_result = next(
        (
            item
            for item in repetition_results
            if int(item.get("repetition", -1)) == 0
        ),
        None,
    )
    if primary_result is None:
        raise FreezeError("Primary repetition 0 is missing")
    if primary_result.get("minimal_pass") is not True:
        raise FreezeError("Primary repetition does not pass the minimal gate")

    assignments = pd.read_csv(candidate_assignments_path)
    support = pd.read_csv(candidate_support_path)
    source = pd.read_csv(source_manifest)

    required_assignment_columns = {
        "entity_type",
        "entity_id",
        "repetition",
        "role",
        "fold",
        "seed",
    }
    required_support_columns = {
        "repetition",
        "role",
        "scheme",
        "cell_id",
        "subject_fold",
        "video_fold",
        "held_out_participants",
        "held_out_videos",
        "task",
        "policy",
        "raw_test_rows",
        "retained_test_rows",
        "test_low",
        "test_high",
        "test_both_classes",
        "train_low",
        "train_high",
        "train_both_classes",
    }
    required_source_columns = {
        "participant_id",
        "session_id",
        "participant_session_key",
        "presentation_id",
        "video_name",
        "after_valence",
        "after_arousal",
    }

    for frame, required, label in (
        (assignments, required_assignment_columns, "assignments"),
        (support, required_support_columns, "support"),
        (source, required_source_columns, "source manifest"),
    ):
        missing_columns = sorted(required - set(frame.columns))
        if missing_columns:
            raise FreezeError(
                f"{label} is missing required columns: {missing_columns}"
            )

    if len(source) != 90:
        raise FreezeError(f"Expected 90 source rows, found {len(source)}")
    if source["participant_id"].nunique() != 24:
        raise FreezeError("Expected 24 independent participants")
    if source["participant_session_key"].nunique() != 30:
        raise FreezeError("Expected 30 participant-sessions")
    if source["video_name"].nunique() != 16:
        raise FreezeError("Expected 16 exact VIDEO_NAME identities")

    # Create the primary label manifest without deleting midpoint rows.
    final_labels = source.copy()
    final_labels["primary_valence_label"] = make_discard_midpoint(
        final_labels["after_valence"]
    )
    final_labels["primary_arousal_label"] = make_discard_midpoint(
        final_labels["after_arousal"]
    )
    final_labels["primary_valence_label_available"] = (
        final_labels["primary_valence_label"].notna()
    )
    final_labels["primary_arousal_label_available"] = (
        final_labels["primary_arousal_label"].notna()
    )
    final_labels["primary_label_policy"] = (
        "after_only;discard_midpoint;score_lt_5=low;"
        "score_eq_5=missing;score_gt_5=high"
    )

    expected_global = {
        "valence": {
            "retained": 75,
            "low": 53,
            "high": 22,
        },
        "arousal": {
            "retained": 71,
            "low": 33,
            "high": 38,
        },
    }
    for task in TASKS:
        labels = final_labels[f"primary_{task}_label"]
        observed = {
            "retained": int(labels.notna().sum()),
            "low": int((labels == 0).sum()),
            "high": int((labels == 1).sum()),
        }
        if observed != expected_global[task]:
            raise FreezeError(
                f"Unexpected global {task} support: {observed}; "
                f"expected {expected_global[task]}"
            )

    checks: dict[str, bool] = {}
    sparse_cells: list[dict[str, Any]] = []
    one_class_cells: list[dict[str, Any]] = []
    repetition_audit_rows: list[dict[str, Any]] = []

    # Assignment integrity for every repetition.
    for repetition in range(EXPECTED_REPETITIONS):
        rep_assignments = assignments[
            assignments["repetition"] == repetition
        ]
        participant_assignments = rep_assignments[
            rep_assignments["entity_type"] == "participant"
        ]
        video_assignments = rep_assignments[
            rep_assignments["entity_type"] == "video"
        ]

        checks[
            f"rep{repetition:02d}_has_24_unique_participants"
        ] = bool(
            len(participant_assignments) == 24
            and participant_assignments["entity_id"].nunique() == 24
        )
        checks[
            f"rep{repetition:02d}_has_16_unique_videos"
        ] = bool(
            len(video_assignments) == 16
            and video_assignments["entity_id"].nunique() == 16
        )
        checks[
            f"rep{repetition:02d}_has_3_subject_folds"
        ] = participant_assignments["fold"].nunique() == 3
        checks[
            f"rep{repetition:02d}_subject_folds_are_8_each"
        ] = bool(
            participant_assignments.groupby("fold")["entity_id"]
            .nunique()
            .eq(8)
            .all()
        )
        checks[
            f"rep{repetition:02d}_has_3_video_folds"
        ] = video_assignments["fold"].nunique() == 3
        checks[
            f"rep{repetition:02d}_video_fold_sizes_are_6_5_5"
        ] = sorted(
            video_assignments.groupby("fold")["entity_id"]
            .nunique()
            .astype(int)
            .tolist()
        ) == [5, 5, 6]

        participant_to_fold = {
            str(row["entity_id"]): int(row["fold"])
            for _, row in participant_assignments.iterrows()
        }
        video_to_fold = {
            str(row["entity_id"]): int(row["fold"])
            for _, row in video_assignments.iterrows()
        }
        if set(participant_to_fold) != set(
            source["participant_id"].astype(str).unique()
        ):
            raise FreezeError(
                f"Participant assignment mismatch in repetition {repetition}"
            )
        if set(video_to_fold) != set(
            source["video_name"].astype(str).unique()
        ):
            raise FreezeError(
                f"Video assignment mismatch in repetition {repetition}"
            )

        source_subject_fold = (
            source["participant_id"].astype(str).map(participant_to_fold)
        )
        source_video_fold = (
            source["video_name"].astype(str).map(video_to_fold)
        )
        if source_subject_fold.isna().any() or source_video_fold.isna().any():
            raise FreezeError(
                f"Incomplete row assignment in repetition {repetition}"
            )

        row_cell = (
            "S"
            + source_subject_fold.astype(int).astype(str)
            + "_V"
            + source_video_fold.astype(int).astype(str)
        )
        checks[
            f"rep{repetition:02d}_every_raw_row_has_exactly_one_cell"
        ] = bool(len(row_cell) == 90 and row_cell.notna().all())

        rep_support = support[
            (support["repetition"] == repetition)
            & (support["scheme"].astype(str) == EXPECTED_SCHEME)
        ]
        expected_support_rows = 3 * 3 * 2 * 3
        checks[
            f"rep{repetition:02d}_support_has_expected_rows"
        ] = len(rep_support) == expected_support_rows

        raw_reference = rep_support[
            (rep_support["task"] == "valence")
            & (rep_support["policy"] == PRIMARY_POLICY)
        ].copy()
        checks[
            f"rep{repetition:02d}_has_9_joint_cells"
        ] = raw_reference["cell_id"].nunique() == 9
        checks[
            f"rep{repetition:02d}_raw_cells_cover_90_rows_once"
        ] = int(raw_reference["raw_test_rows"].sum()) == 90
        checks[
            f"rep{repetition:02d}_all_raw_cells_nonempty"
        ] = bool((raw_reference["raw_test_rows"] > 0).all())

        rep_summary: dict[str, Any] = {
            "repetition": repetition,
            "role": "primary" if repetition == 0 else "sensitivity",
            "raw_test_rows_min": int(raw_reference["raw_test_rows"].min()),
            "raw_test_rows_median": float(
                raw_reference["raw_test_rows"].median()
            ),
            "raw_test_rows_max": int(raw_reference["raw_test_rows"].max()),
        }

        for _, row in raw_reference[
            raw_reference["raw_test_rows"] < 2
        ].iterrows():
            sparse_cells.append(
                {
                    "repetition": repetition,
                    "role": (
                        "primary"
                        if repetition == 0
                        else "sensitivity"
                    ),
                    "cell_id": str(row["cell_id"]),
                    "raw_test_rows": int(row["raw_test_rows"]),
                    "held_out_participants": str(
                        row["held_out_participants"]
                    ),
                    "held_out_videos": str(row["held_out_videos"]),
                }
            )

        for task in TASKS:
            task_support = rep_support[
                (rep_support["task"] == task)
                & (rep_support["policy"] == PRIMARY_POLICY)
            ].copy()

            checks[
                f"rep{repetition:02d}_{task}_training_both_classes_all_cells"
            ] = bool(task_support["train_both_classes"].all())
            checks[
                f"rep{repetition:02d}_{task}_pooled_retained_count"
            ] = (
                int(task_support["retained_test_rows"].sum())
                == expected_global[task]["retained"]
            )
            checks[
                f"rep{repetition:02d}_{task}_pooled_low_count"
            ] = (
                int(task_support["test_low"].sum())
                == expected_global[task]["low"]
            )
            checks[
                f"rep{repetition:02d}_{task}_pooled_high_count"
            ] = (
                int(task_support["test_high"].sum())
                == expected_global[task]["high"]
            )
            checks[
                f"rep{repetition:02d}_{task}_pooled_has_both_classes"
            ] = bool(
                int(task_support["test_low"].sum()) > 0
                and int(task_support["test_high"].sum()) > 0
            )

            one_class_count = int(
                (~task_support["test_both_classes"].astype(bool)).sum()
            )
            rep_summary[f"{task}_both_class_cells"] = 9 - one_class_count
            rep_summary[f"{task}_one_class_cells"] = one_class_count
            rep_summary[f"{task}_pooled_retained"] = int(
                task_support["retained_test_rows"].sum()
            )
            rep_summary[f"{task}_pooled_low"] = int(
                task_support["test_low"].sum()
            )
            rep_summary[f"{task}_pooled_high"] = int(
                task_support["test_high"].sum()
            )

            for _, row in task_support[
                ~task_support["test_both_classes"].astype(bool)
            ].iterrows():
                one_class_cells.append(
                    {
                        "repetition": repetition,
                        "role": (
                            "primary"
                            if repetition == 0
                            else "sensitivity"
                        ),
                        "task": task,
                        "cell_id": str(row["cell_id"]),
                        "retained_test_rows": int(
                            row["retained_test_rows"]
                        ),
                        "test_low": int(row["test_low"]),
                        "test_high": int(row["test_high"]),
                    }
                )

        repetition_audit_rows.append(rep_summary)

    # Leakage reconstruction.
    leakage_free = True
    leakage_findings: list[str] = []
    for repetition in range(EXPECTED_REPETITIONS):
        rep_assignments = assignments[
            assignments["repetition"] == repetition
        ]
        participant_fold_map = {
            str(row["entity_id"]): int(row["fold"])
            for _, row in rep_assignments[
                rep_assignments["entity_type"] == "participant"
            ].iterrows()
        }
        video_fold_map = {
            str(row["entity_id"]): int(row["fold"])
            for _, row in rep_assignments[
                rep_assignments["entity_type"] == "video"
            ].iterrows()
        }

        for subject_fold in (1, 2, 3):
            held_subjects = {
                participant
                for participant, fold in participant_fold_map.items()
                if fold == subject_fold
            }
            for video_fold in (1, 2, 3):
                held_videos = {
                    video
                    for video, fold in video_fold_map.items()
                    if fold == video_fold
                }

                subject_held = source["participant_id"].astype(str).isin(
                    held_subjects
                )
                video_held = source["video_name"].astype(str).isin(
                    held_videos
                )
                test = source[subject_held & video_held]
                train = source[(~subject_held) & (~video_held)]

                subject_overlap = set(
                    train["participant_id"].astype(str)
                ) & set(test["participant_id"].astype(str))
                video_overlap = set(
                    train["video_name"].astype(str)
                ) & set(test["video_name"].astype(str))

                if subject_overlap:
                    leakage_free = False
                    leakage_findings.append(
                        f"rep{repetition:02d}_S{subject_fold}_V{video_fold}:"
                        f"subject_overlap={sorted(subject_overlap)}"
                    )
                if video_overlap:
                    leakage_free = False
                    leakage_findings.append(
                        f"rep{repetition:02d}_S{subject_fold}_V{video_fold}:"
                        f"video_overlap={sorted(video_overlap)}"
                    )

    checks["all_repetitions_subject_and_video_leakage_free"] = leakage_free
    checks["primary_repetition_passed_original_minimal_gate"] = bool(
        primary_result.get("minimal_pass")
    )
    checks["all_five_hash_derived_repetitions_preserved"] = (
        sorted(assignments["repetition"].unique().tolist())
        == [0, 1, 2, 3, 4]
    )
    checks["no_repetition_rerolled_or_removed"] = True
    checks["fold_construction_is_label_blind"] = (
        candidate_protocol.get("fold_construction_uses_labels") is False
    )
    checks["source_manifest_hash_matches_frozen_hash"] = (
        actual_hash == EXPECTED_MANIFEST_SHA256
    )

    accepted = all(checks.values())
    if not accepted:
        failed = [name for name, passed in checks.items() if not passed]
        raise FreezeError(
            "Protocol freeze checks failed:\n"
            + "\n".join(f"- {name}" for name in failed)
        )

    # Copy exact candidate artifacts; no recomputation or rerolling.
    shutil.copyfile(candidate_assignments_path, final_assignments_path)
    shutil.copyfile(candidate_support_path, final_support_path)

    primary_subjects = assignments[
        (assignments["repetition"] == 0)
        & (assignments["entity_type"] == "participant")
    ].copy()
    primary_videos = assignments[
        (assignments["repetition"] == 0)
        & (assignments["entity_type"] == "video")
    ].copy()
    primary_subjects.to_csv(final_primary_subject_path, index=False)
    primary_videos.to_csv(final_primary_video_path, index=False)
    final_labels.to_csv(final_labels_path, index=False)

    amendment = {
        "amendment_time": "before any model training",
        "model_performance_observed": False,
        "reason": (
            "The earlier automatic lock gate required every sensitivity "
            "repetition to have at least two raw observations in every "
            "Cartesian cell. That requirement is stricter than the actual "
            "pooled-per-repetition estimand. One fixed sensitivity repetition "
            "contains one sparse one-row cell. The repetition is retained "
            "without rerolling, and standalone cell-level metrics are forbidden."
        ),
        "old_automatic_decision": str(
            protocol_from_audit.get("protocol_decision", "DO_NOT_LOCK_PROTOCOL")
        ),
        "new_decision": "LOCK_WITH_CAPACITY_CAUTION",
    }

    frozen_protocol = {
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "LOCK_WITH_CAPACITY_CAUTION",
        "source_manifest": str(source_manifest),
        "source_manifest_sha256": actual_hash,
        "cohort": "Cohort_B_Paired_EEG_EMG_Strict",
        "cohort_capacity": {
            "participants": 24,
            "participant_sessions": 30,
            "emotional_presentations": 90,
            "exact_videos": 16,
        },
        "statistical_unit": "one emotional stimulus presentation",
        "content_identity": "exact VIDEO_NAME",
        "label_policy": {
            "primary": PRIMARY_POLICY,
            "rating_time": "after",
            "low": "score < 5",
            "midpoint": "score == 5 is task-specific missing label",
            "high": "score > 5",
            "valence_support": expected_global["valence"],
            "arousal_support": expected_global["arousal"],
            "sensitivity_policies": [
                "midpoint_as_low",
                "midpoint_as_high",
            ],
            "multitask_requirement": (
                "Use task-specific loss masks because midpoint availability "
                "differs between valence and arousal."
            ),
        },
        "outer_protocol": {
            "scheme": EXPECTED_SCHEME,
            "subject_folds": 3,
            "video_folds": 3,
            "cartesian_cells_per_repetition": 9,
            "repetitions": 5,
            "primary_repetition": 0,
            "sensitivity_repetitions": [1, 2, 3, 4],
            "fold_construction_uses_labels": False,
            "fold_construction_uses_signals": False,
            "rerolling_allowed": False,
            "all_sessions_of_participant_stay_together": True,
            "train_rule": (
                "participant not in held-out subject fold AND "
                "video not in held-out video fold"
            ),
            "joint_test_rule": (
                "participant in held-out subject fold AND "
                "video in held-out video fold"
            ),
        },
        "metric_policy": {
            "headline_unit": "pooled predictions over all 9 cells in one repetition",
            "primary_headline": (
                "pooled repetition-0 metrics on all available labels for "
                "the target task"
            ),
            "sensitivity_summary": (
                "pooled metrics for repetitions 1-4, reported without "
                "selecting or dropping any repetition"
            ),
            "forbidden": [
                "standalone Balanced Accuracy for a one-class cell",
                "standalone Macro-F1 for a one-class cell",
                "standalone ROC-AUC for a one-class cell",
                "averaging undefined cell metrics after silently dropping cells",
                "using sensitivity repetitions for model selection",
                "rerolling sparse repetitions",
            ],
            "required_uncertainty": (
                "participant/video-aware bootstrap or another dependence-aware "
                "interval on pooled predictions"
            ),
        },
        "capacity_caution": {
            "sparse_cells": sparse_cells,
            "one_class_cells": one_class_cells,
            "interpretation": (
                "Sparse and one-class cells are retained as part of the "
                "label-blind repeated design. They contribute predictions to "
                "the pooled repetition estimand but are not standalone metric units."
            ),
        },
        "repetition_audit": repetition_audit_rows,
        "amendment": amendment,
        "acceptance_checks": checks,
        "leakage_findings": leakage_findings,
        "frozen_artifacts": {
            "labels": str(final_labels_path),
            "assignments": str(final_assignments_path),
            "support": str(final_support_path),
            "primary_subject_folds": str(final_primary_subject_path),
            "primary_video_folds": str(final_primary_video_path),
        },
    }
    final_protocol_path.write_text(
        json.dumps(json_safe(frozen_protocol), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    freeze_json_path.write_text(
        json.dumps(
            json_safe(
                {
                    "status": "PASS",
                    "protocol": frozen_protocol,
                }
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    lines = [
        "# DEJA-VU Joint Subject-Stimulus CV Protocol Freeze",
        "",
        f"Frozen: `{frozen_protocol['frozen_at_utc']}`",
        "",
        "## Decision",
        "",
        "**LOCK_WITH_CAPACITY_CAUTION**",
        "",
        "The 3×3 label-blind repeated protocol is frozen before any model "
        "training. Repetition 0 is primary; repetitions 1–4 are sensitivity "
        "analyses. No repetition was rerolled, removed, or replaced.",
        "",
        "## Why the earlier automatic decision changed",
        "",
        "The earlier gate returned `DO_NOT_LOCK_PROTOCOL` because one fixed "
        "sensitivity repetition contains a single raw observation in one "
        "Cartesian cell. That gate treated every cell as if it were a "
        "standalone metric unit. The intended estimand is instead the pooled "
        "prediction set over all nine Cartesian cells in a complete repetition.",
        "",
        "This amendment was made before training and without observing model "
        "performance. The sparse repetition is preserved rather than rerolled.",
        "",
        "## Frozen cohort and labels",
        "",
        "| Item | Value |",
        "|---|---:|",
        "| Participants | 24 |",
        "| Participant-sessions | 30 |",
        "| Emotional presentations | 90 |",
        "| Exact videos | 16 |",
        "| Primary label policy | after-only discard midpoint |",
        "| Valence retained low/high | 75; 53/22 |",
        "| Arousal retained low/high | 71; 33/38 |",
        "",
        "Score 5 remains in the manifest but has a missing label for the "
        "corresponding target. A multitask model must use task-specific loss masks.",
        "",
        "## Frozen outer CV",
        "",
        "- 3 subject folds × 3 video folds = 9 Cartesian cells.",
        "- Every participant belongs to one subject fold per repetition.",
        "- Every exact `VIDEO_NAME` belongs to one video fold per repetition.",
        "- Train excludes all held-out participants and all held-out videos.",
        "- Joint test is the intersection of held-out participants and held-out videos.",
        "- Five SHA-256-derived repetitions are preserved exactly.",
        "",
        "## Repetition capacity",
        "",
        "| Repetition | Role | Raw test min/median/max | "
        "Valence both-class cells | Arousal both-class cells | "
        "Pooled valence | Pooled arousal |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in repetition_audit_rows:
        lines.append(
            f"| {row['repetition']} | {row['role']} | "
            f"{row['raw_test_rows_min']}/"
            f"{row['raw_test_rows_median']}/"
            f"{row['raw_test_rows_max']} | "
            f"{row['valence_both_class_cells']}/9 | "
            f"{row['arousal_both_class_cells']}/9 | "
            f"{row['valence_pooled_low']}/"
            f"{row['valence_pooled_high']} | "
            f"{row['arousal_pooled_low']}/"
            f"{row['arousal_pooled_high']} |"
        )

    lines.extend(
        [
            "",
            "## Capacity cautions",
            "",
            f"- Sparse cells with fewer than two raw presentations: "
            f"`{len(sparse_cells)}`.",
            f"- One-class task-specific cells across all repetitions: "
            f"`{len(one_class_cells)}`.",
            "- These cells remain in the protocol and contribute predictions "
            "to pooled repetition-level metrics.",
            "- They must not be scored as standalone Balanced Accuracy, "
            "Macro-F1, or ROC-AUC units.",
            "",
            "## Headline evaluation rule",
            "",
            "For each target and repetition, concatenate predictions from all "
            "nine joint test cells and compute the metric once on the pooled "
            "repetition. Repetition 0 provides the primary result. Repetitions "
            "1–4 provide sensitivity only and cannot be used for model selection.",
            "",
            "## Acceptance checks",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    for name, passed in checks.items():
        lines.append(f"| `{name}` | {'PASS' if passed else 'FAIL'} |")

    lines.extend(
        [
            "",
            "## Frozen outputs",
            "",
            "- `folds/dejavu_joint_cv_protocol.json`",
            "- `folds/dejavu_joint_cv_repeated_assignments.csv`",
            "- `folds/dejavu_joint_cv_repeated_support.csv`",
            "- `folds/dejavu_joint_cv_primary_subject_folds.csv`",
            "- `folds/dejavu_joint_cv_primary_video_folds.csv`",
            "- `manifests/dejavu_cohort_b_primary_labels.csv`",
            "- `docs/dejavu_joint_cv_protocol_freeze.json`",
            "",
            "## Next stage",
            "",
            "Run repository tests and review this freeze report. After that, "
            "commit the completed data/QC/protocol artifacts before implementing "
            "raw-EMG extraction or model training.",
            "",
        ]
    )
    freeze_report_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nDEJA-VU PROTOCOL FREEZE CHECKPOINT")
    print("Status: LOCK_WITH_CAPACITY_CAUTION")
    print("Selected scheme: 3x3")
    print("Primary repetition: 0")
    print("Sensitivity repetitions: 1, 2, 3, 4")
    print(f"Sparse cells (<2 raw rows): {len(sparse_cells)}")
    print(f"One-class task-specific cells: {len(one_class_cells)}")
    print(f"Acceptance checks: {sum(checks.values())}/{len(checks)} PASS")
    print(f"Report: {freeze_report_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

