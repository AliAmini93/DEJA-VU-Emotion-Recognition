#!/usr/bin/env python3
"""Audit binary valence/arousal label-policy capacity for DEJA-VU Cohort B.

Read-only against:
- the accepted Cohort B emotional-presentation manifest;
- the official SQLite ratings table.

No training, fold construction, performance-based policy selection, commit,
or push is performed.

Evaluated policies, using post-stimulus ("after") self-ratings only:
- discard_midpoint: score 5 removed; <5 low, >5 high
- midpoint_as_low: <=5 low, >5 high
- midpoint_as_high: <5 low, >=5 high
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


TASKS = ("valence", "arousal")
POLICIES = ("discard_midpoint", "midpoint_as_low", "midpoint_as_high")


class AuditError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    return parser.parse_args()


def make_binary(scores: pd.Series, policy: str) -> pd.Series:
    numeric = pd.to_numeric(scores, errors="coerce")
    if policy == "discard_midpoint":
        values = np.where(
            numeric < 5,
            0,
            np.where(numeric > 5, 1, np.nan),
        )
    elif policy == "midpoint_as_low":
        values = np.where(numeric <= 5, 0, 1)
        values = np.where(numeric.isna(), np.nan, values)
    elif policy == "midpoint_as_high":
        values = np.where(numeric < 5, 0, 1)
        values = np.where(numeric.isna(), np.nan, values)
    else:
        raise ValueError(policy)
    return pd.Series(values, index=scores.index, dtype="Float64").astype("Int64")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def support_class(participants: int) -> str:
    if participants <= 1:
        return "SINGLETON"
    if participants <= 3:
        return "SPARSE"
    if participants <= 5:
        return "MODERATE"
    return "STRONG"


def summarize_group(
    frame: pd.DataFrame,
    group_col: str,
    task: str,
    policy: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_value, group in frame.groupby(group_col, dropna=False):
        labels = group["binary_label"].dropna().astype(int)
        low = int((labels == 0).sum())
        high = int((labels == 1).sum())
        retained = int(len(labels))
        participants = int(group["participant_id"].nunique())
        sessions = int(group["participant_session_key"].nunique())
        videos = int(group["video_name"].nunique())
        rows.append(
            {
                "task": task,
                "policy": policy,
                group_col: group_value,
                "available_rows": int(len(group)),
                "retained_rows": retained,
                "dropped_rows": int(len(group) - retained),
                "low_count": low,
                "high_count": high,
                "both_classes": bool(labels.nunique() == 2),
                "single_class": bool(retained > 0 and labels.nunique() == 1),
                "no_retained_rows": bool(retained == 0),
                "participants": participants,
                "participant_sessions": sessions,
                "videos": videos,
                "support_class": support_class(participants)
                if group_col == "video_name"
                else "",
                "canonical_quadrants": ";".join(
                    sorted(group["canonical_quadrant"].dropna().astype(str).unique())
                ),
                "emotion_names": ";".join(
                    sorted(group["emotion_name"].dropna().astype(str).unique())
                ),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    manifests_dir = repo_root / "manifests"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    cohort_path = manifests_dir / "dejavu_cohort_b_emotional_presentations.csv"
    db_path = (
        data_root
        / "extracted"
        / "dataset"
        / "DEJA-VU"
        / "deja_vu_database.db"
    )

    if not cohort_path.exists():
        raise AuditError(f"Cohort B emotional manifest not found: {cohort_path}")
    if not db_path.exists():
        raise AuditError(f"SQLite database not found: {db_path}")

    cohort = pd.read_csv(cohort_path)
    required = {
        "participant_id",
        "session_id",
        "participant_session_key",
        "presentation_id",
        "video_name",
        "canonical_quadrant",
        "emotion_name",
    }
    missing = sorted(required - set(cohort.columns))
    if missing:
        raise AuditError(f"Cohort B manifest missing columns: {missing}")

    if len(cohort) != 90:
        raise AuditError(f"Expected 90 emotional presentations, found {len(cohort)}")
    if cohort["participant_id"].nunique() != 24:
        raise AuditError(
            f"Expected 24 participants, found {cohort['participant_id'].nunique()}"
        )
    if cohort["participant_session_key"].nunique() != 30:
        raise AuditError(
            "Expected 30 participant-sessions, found "
            f"{cohort['participant_session_key'].nunique()}"
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    ratings = pd.read_sql_query(
        """
        SELECT
            subject AS participant_id,
            session AS session_id,
            video_name,
            rating_time,
            rating_valence,
            rating_arousal,
            rating_dominance
        FROM ratings
        ORDER BY subject, session, video_name, rating_time
        """,
        conn,
    )
    conn.close()

    ratings["participant_id"] = ratings["participant_id"].astype(str)
    ratings["session_id"] = ratings["session_id"].astype(str)
    ratings["rating_time"] = ratings["rating_time"].astype(str).str.strip().str.lower()

    duplicate_check = (
        ratings.groupby(
            ["participant_id", "session_id", "video_name", "rating_time"],
            dropna=False,
        )
        .size()
        .rename("count")
        .reset_index()
    )
    duplicates = duplicate_check[duplicate_check["count"] != 1]
    if not duplicates.empty:
        raise AuditError(
            "Ratings are not unique per participant/session/video/time: "
            + duplicates.to_json(orient="records")
        )

    after = ratings[ratings["rating_time"] == "after"].copy()
    before = ratings[ratings["rating_time"] == "before"].copy()

    if len(after) != 136 or len(before) != 136:
        raise AuditError(
            "Expected 136 before and 136 after rows; found "
            f"before={len(before)}, after={len(after)}"
        )

    after = after.rename(
        columns={
            "rating_valence": "after_valence",
            "rating_arousal": "after_arousal",
            "rating_dominance": "after_dominance",
        }
    )[
        [
            "participant_id",
            "session_id",
            "video_name",
            "after_valence",
            "after_arousal",
            "after_dominance",
        ]
    ]

    before = before.rename(
        columns={
            "rating_valence": "before_valence",
            "rating_arousal": "before_arousal",
            "rating_dominance": "before_dominance",
        }
    )[
        [
            "participant_id",
            "session_id",
            "video_name",
            "before_valence",
            "before_arousal",
            "before_dominance",
        ]
    ]

    enriched = cohort.merge(
        before,
        on=["participant_id", "session_id", "video_name"],
        how="left",
        validate="one_to_one",
    ).merge(
        after,
        on=["participant_id", "session_id", "video_name"],
        how="left",
        validate="one_to_one",
    )

    rating_columns = (
        "before_valence",
        "before_arousal",
        "before_dominance",
        "after_valence",
        "after_arousal",
        "after_dominance",
    )
    if enriched[list(rating_columns)].isna().any().any():
        bad = enriched.loc[
            enriched[list(rating_columns)].isna().any(axis=1),
            ["presentation_id", "participant_id", "session_id", "video_name"],
        ]
        raise AuditError(
            "Missing rating join rows: " + bad.to_json(orient="records")
        )

    for column in rating_columns:
        values = pd.to_numeric(enriched[column], errors="coerce")
        if values.isna().any() or not values.between(1, 9).all():
            raise AuditError(f"Invalid 1-9 rating values in {column}")
        enriched[column] = values.astype(int)

    summary_rows: list[dict[str, Any]] = []
    participant_frames: list[pd.DataFrame] = []
    session_frames: list[pd.DataFrame] = []
    video_frames: list[pd.DataFrame] = []

    for task in TASKS:
        score_col = f"after_{task}"
        for policy in POLICIES:
            working = enriched.copy()
            working["binary_label"] = make_binary(working[score_col], policy)
            retained = working[working["binary_label"].notna()].copy()
            labels = retained["binary_label"].astype(int)

            participant_support = summarize_group(
                working, "participant_id", task, policy
            )
            session_support = summarize_group(
                working, "participant_session_key", task, policy
            )
            video_support = summarize_group(
                working, "video_name", task, policy
            )

            low = int((labels == 0).sum())
            high = int((labels == 1).sum())
            retained_count = int(len(retained))
            midpoint_count = int((working[score_col] == 5).sum())
            majority = (
                max(low, high) / retained_count if retained_count else None
            )

            summary_rows.append(
                {
                    "task": task,
                    "policy": policy,
                    "available_rows": int(len(working)),
                    "retained_rows": retained_count,
                    "dropped_rows": int(len(working) - retained_count),
                    "midpoint_rows": midpoint_count,
                    "low_count": low,
                    "high_count": high,
                    "low_fraction": low / retained_count
                    if retained_count
                    else None,
                    "high_fraction": high / retained_count
                    if retained_count
                    else None,
                    "majority_accuracy_baseline": majority,
                    "uniform_random_accuracy_reference": 0.5,
                    "participants_retained": int(
                        retained["participant_id"].nunique()
                    ),
                    "participant_sessions_retained": int(
                        retained["participant_session_key"].nunique()
                    ),
                    "videos_retained": int(
                        retained["video_name"].nunique()
                    ),
                    "participants_with_both_classes": int(
                        participant_support["both_classes"].sum()
                    ),
                    "single_class_participants": int(
                        participant_support["single_class"].sum()
                    ),
                    "sessions_with_both_classes": int(
                        session_support["both_classes"].sum()
                    ),
                    "single_class_sessions": int(
                        session_support["single_class"].sum()
                    ),
                    "videos_with_both_classes": int(
                        video_support["both_classes"].sum()
                    ),
                    "single_class_videos": int(
                        video_support["single_class"].sum()
                    ),
                    "singleton_participant_videos": int(
                        (video_support["participants"] == 1).sum()
                    ),
                    "videos_with_at_least_2_participants": int(
                        (video_support["participants"] >= 2).sum()
                    ),
                    "minimum_video_retained_rows": int(
                        video_support["retained_rows"].min()
                    ),
                    "median_video_retained_rows": float(
                        video_support["retained_rows"].median()
                    ),
                    "maximum_video_retained_rows": int(
                        video_support["retained_rows"].max()
                    ),
                }
            )

            participant_frames.append(participant_support)
            session_frames.append(session_support)
            video_frames.append(video_support)

            enriched[f"after_{task}_{policy}_label"] = make_binary(
                enriched[score_col], policy
            )

    summary_df = pd.DataFrame(summary_rows)
    participant_df = pd.concat(participant_frames, ignore_index=True)
    session_df = pd.concat(session_frames, ignore_index=True)
    video_df = pd.concat(video_frames, ignore_index=True)

    candidate_manifest_path = (
        manifests_dir / "dejavu_cohort_b_emotional_label_candidates.csv"
    )
    summary_path = docs_dir / "dejavu_cohort_b_label_policy_summary.csv"
    participant_path = (
        docs_dir / "dejavu_cohort_b_label_policy_by_participant.csv"
    )
    session_path = (
        docs_dir / "dejavu_cohort_b_label_policy_by_session.csv"
    )
    video_path = docs_dir / "dejavu_cohort_b_label_policy_by_video.csv"

    enriched.to_csv(candidate_manifest_path, index=False)
    summary_df.to_csv(summary_path, index=False)
    participant_df.to_csv(participant_path, index=False)
    session_df.to_csv(session_path, index=False)
    video_df.to_csv(video_path, index=False)

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cohort": "Cohort_B_Paired_EEG_EMG_Strict",
        "participants": 24,
        "participant_sessions": 30,
        "emotional_presentations": 90,
        "unique_videos": int(enriched["video_name"].nunique()),
        "rating_timing": "after_only",
        "rating_scale": "1-9 integer",
        "midpoint": 5,
        "tasks": list(TASKS),
        "policies": list(POLICIES),
        "policy_selected": None,
        "summary": summary_rows,
        "source_manifest": str(cohort_path),
        "source_database": str(db_path),
    }
    json_path = docs_dir / "dejavu_cohort_b_label_policy_audit.json"
    json_path.write_text(
        json.dumps(json_safe(metadata), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = docs_dir / "dejavu_cohort_b_label_policy_audit.md"
    lines = [
        "# DEJA-VU Cohort B Label-Policy Capacity Audit",
        "",
        f"Generated: `{metadata['generated_at_utc']}`",
        "",
        "Scope: the accepted strict paired EEG+EMG cohort only "
        "(24 participants, 30 participant-sessions, 90 emotional presentations).",
        "",
        "Only post-stimulus (`after`) self-ratings are evaluated. "
        "No policy is selected in this audit.",
        "",
        "## Policy capacity",
        "",
        "| Task | Policy | Retained | Dropped | Low | High | Majority baseline | "
        "Participants both classes | Single-class participants | "
        "Sessions both classes | Single-class sessions | "
        "Videos both classes | Single-class videos | Singleton videos |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for _, row in summary_df.iterrows():
        majority = (
            ""
            if pd.isna(row["majority_accuracy_baseline"])
            else f"{float(row['majority_accuracy_baseline']):.4f}"
        )
        lines.append(
            f"| {row['task']} | {row['policy']} | "
            f"{int(row['retained_rows'])} | {int(row['dropped_rows'])} | "
            f"{int(row['low_count'])} | {int(row['high_count'])} | "
            f"{majority} | "
            f"{int(row['participants_with_both_classes'])} | "
            f"{int(row['single_class_participants'])} | "
            f"{int(row['sessions_with_both_classes'])} | "
            f"{int(row['single_class_sessions'])} | "
            f"{int(row['videos_with_both_classes'])} | "
            f"{int(row['single_class_videos'])} | "
            f"{int(row['singleton_participant_videos'])} |"
        )

    lines.extend(
        [
            "",
            "## Definitions",
            "",
            "- `discard_midpoint`: score 5 is removed; `<5=low`, `>5=high`.",
            "- `midpoint_as_low`: `<=5=low`, `>5=high`.",
            "- `midpoint_as_high`: `<5=low`, `>=5=high`.",
            "- Majority baseline is descriptive only and is not a model result.",
            "",
            "## Constraints for the next stage",
            "",
            "- `VIDEO_NAME` remains the held-out content identity.",
            "- Four videos are represented by only one participant; those videos "
            "cannot support a strong standalone held-out-content test fold.",
            "- A policy must not be selected merely because it gives a convenient "
            "class balance or future model result.",
            "- Final Joint Subject-Stimulus CV construction remains blocked until "
            "this report is reviewed.",
            "",
            "## Outputs",
            "",
            "- `manifests/dejavu_cohort_b_emotional_label_candidates.csv`",
            "- `docs/dejavu_cohort_b_label_policy_summary.csv`",
            "- `docs/dejavu_cohort_b_label_policy_by_participant.csv`",
            "- `docs/dejavu_cohort_b_label_policy_by_session.csv`",
            "- `docs/dejavu_cohort_b_label_policy_by_video.csv`",
            "- `docs/dejavu_cohort_b_label_policy_audit.json`",
            "",
            "## Decision",
            "",
            "**Final binary valence policy: NOT SELECTED.**  ",
            "**Final binary arousal policy: NOT SELECTED.**",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nDEJA-VU COHORT B LABEL POLICY CHECKPOINT")
    print("Participants: 24")
    print("Participant-sessions: 30")
    print("Emotional presentations: 90")
    print("Unique videos:", int(enriched["video_name"].nunique()))
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

