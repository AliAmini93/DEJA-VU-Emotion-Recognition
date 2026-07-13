#!/usr/bin/env python3
"""Freeze and validate the strict paired EEG+EMG Cohort B for DEJA-VU.

This script is read-only against source manifests and dataset files. It creates
new cohort manifests only. A participant-session is included only when:
- exactly 4 stimulus-presentation rows exist;
- all 4 presentations pass strict two-channel raw-EMG QC;
- exactly 3 transition rows exist;
- all 3 transitions pass strict two-channel raw-EMG QC.

No training, preprocessing, fold construction, commit, or push is performed.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EXPECTED_EXCLUDED = {
    "P012_S001",
    "P015_S001",
    "P019_S001",
    "P020_S001",
}


class CohortError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    return parser.parse_args()


def parse_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)

    normalized = series.astype(str).str.strip().str.lower()
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
    unknown = sorted(set(normalized.unique()) - set(mapping))
    if unknown:
        raise CohortError(
            f"Unrecognized boolean values in {series.name}: {unknown}"
        )
    return normalized.map(mapping).astype(bool)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def normalized_session_key(frame: pd.DataFrame) -> pd.Series:
    if "participant_session_key" in frame.columns:
        return frame["participant_session_key"].astype(str)
    return (
        frame["participant_id"].astype(str)
        + "_"
        + frame["session_id"].astype(str)
    )


def require_columns(
    frame: pd.DataFrame, required: set[str], label: str
) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise CohortError(f"{label} is missing columns: {missing}")


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    manifests_dir = repo_root / "manifests"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    source_presentations_path = (
        manifests_dir / "dejavu_stimulus_presentation_emg_strict_qc.csv"
    )
    source_transitions_path = (
        manifests_dir / "dejavu_transition_emg_strict_qc.csv"
    )

    for path in (source_presentations_path, source_transitions_path):
        if not path.exists():
            raise CohortError(f"Required source manifest not found: {path}")

    presentations = pd.read_csv(source_presentations_path)
    transitions = pd.read_csv(source_transitions_path)

    require_columns(
        presentations,
        {
            "participant_id",
            "session_id",
            "chronological_position",
            "presentation_id",
            "video_name",
            "canonical_quadrant",
            "emotion_name",
            "is_baseline",
            "is_emotional_stimulus",
            "strict_two_channel_emg_eligible",
        },
        "presentation manifest",
    )
    require_columns(
        transitions,
        {
            "participant_id",
            "session_id",
            "transition_position",
            "transition_type",
            "strict_two_channel_emg_eligible",
        },
        "transition manifest",
    )

    presentations["participant_session_key"] = normalized_session_key(
        presentations
    )
    transitions["participant_session_key"] = normalized_session_key(
        transitions
    )

    presentations["strict_two_channel_emg_eligible"] = parse_bool(
        presentations["strict_two_channel_emg_eligible"]
    )
    transitions["strict_two_channel_emg_eligible"] = parse_bool(
        transitions["strict_two_channel_emg_eligible"]
    )
    presentations["is_baseline"] = parse_bool(
        presentations["is_baseline"]
    )
    presentations["is_emotional_stimulus"] = parse_bool(
        presentations["is_emotional_stimulus"]
    )

    presentation_keys = set(presentations["participant_session_key"])
    transition_keys = set(transitions["participant_session_key"])
    all_keys = sorted(presentation_keys | transition_keys)

    session_rows: list[dict[str, Any]] = []
    for key in all_keys:
        p = presentations[
            presentations["participant_session_key"] == key
        ].copy()
        t = transitions[
            transitions["participant_session_key"] == key
        ].copy()

        if len(p):
            participant_id = str(p["participant_id"].iloc[0])
            session_id = str(p["session_id"].iloc[0])
        elif len(t):
            participant_id = str(t["participant_id"].iloc[0])
            session_id = str(t["session_id"].iloc[0])
        else:
            raise AssertionError(key)

        p_count_ok = len(p) == 4
        t_count_ok = len(t) == 3
        p_strict_count = int(
            p["strict_two_channel_emg_eligible"].sum()
        )
        t_strict_count = int(
            t["strict_two_channel_emg_eligible"].sum()
        )
        p_all_strict = bool(
            p_count_ok
            and p["strict_two_channel_emg_eligible"].all()
        )
        t_all_strict = bool(
            t_count_ok
            and t["strict_two_channel_emg_eligible"].all()
        )
        include = bool(
            p_count_ok
            and t_count_ok
            and p_all_strict
            and t_all_strict
        )

        reasons: list[str] = []
        if not p_count_ok:
            reasons.append(f"PRESENTATION_COUNT_{len(p)}")
        if not t_count_ok:
            reasons.append(f"TRANSITION_COUNT_{len(t)}")
        if p_count_ok and not p_all_strict:
            reasons.append(
                f"PRESENTATION_STRICT_FAIL_{len(p)-p_strict_count}"
            )
        if t_count_ok and not t_all_strict:
            reasons.append(
                f"TRANSITION_STRICT_FAIL_{len(t)-t_strict_count}"
            )

        session_rows.append(
            {
                "dataset": "DEJA-VU",
                "cohort": "Cohort_B_Paired_EEG_EMG_Strict",
                "participant_id": participant_id,
                "session_id": session_id,
                "participant_session_key": key,
                "presentation_rows": int(len(p)),
                "strict_presentation_rows": p_strict_count,
                "transition_rows": int(len(t)),
                "strict_transition_rows": t_strict_count,
                "include_in_cohort_b": include,
                "exclusion_reason": (
                    "" if include else ";".join(reasons)
                ),
            }
        )

    sessions = pd.DataFrame(session_rows).sort_values(
        ["participant_id", "session_id"]
    )
    included_sessions = set(
        sessions.loc[
            sessions["include_in_cohort_b"],
            "participant_session_key",
        ]
    )
    excluded_sessions = set(
        sessions.loc[
            ~sessions["include_in_cohort_b"],
            "participant_session_key",
        ]
    )

    cohort_presentations = presentations[
        presentations["participant_session_key"].isin(included_sessions)
    ].copy()
    cohort_transitions = transitions[
        transitions["participant_session_key"].isin(included_sessions)
    ].copy()
    cohort_emotional = cohort_presentations[
        cohort_presentations["is_emotional_stimulus"]
    ].copy()
    cohort_baseline = cohort_presentations[
        cohort_presentations["is_baseline"]
    ].copy()

    cohort_presentations.insert(
        1, "cohort", "Cohort_B_Paired_EEG_EMG_Strict"
    )
    cohort_transitions.insert(
        1, "cohort", "Cohort_B_Paired_EEG_EMG_Strict"
    )
    cohort_emotional.insert(
        1, "cohort", "Cohort_B_Paired_EEG_EMG_Strict"
    )

    # Compare video support before and after strict session exclusion.
    full_emotional = presentations[
        presentations["is_emotional_stimulus"]
    ].copy()

    full_support = (
        full_emotional.groupby("video_name", dropna=False)
        .agg(
            full_presentations=("presentation_id", "size"),
            full_participants=("participant_id", "nunique"),
            full_sessions=("participant_session_key", "nunique"),
            canonical_quadrant=(
                "canonical_quadrant",
                lambda x: ";".join(
                    sorted(x.dropna().astype(str).unique())
                ),
            ),
            emotion_name=(
                "emotion_name",
                lambda x: ";".join(
                    sorted(x.dropna().astype(str).unique())
                ),
            ),
        )
        .reset_index()
    )

    cohort_support = (
        cohort_emotional.groupby("video_name", dropna=False)
        .agg(
            cohort_b_presentations=("presentation_id", "size"),
            cohort_b_participants=("participant_id", "nunique"),
            cohort_b_sessions=("participant_session_key", "nunique"),
        )
        .reset_index()
    )

    video_support = full_support.merge(
        cohort_support,
        on="video_name",
        how="left",
        validate="one_to_one",
    )
    for column in (
        "cohort_b_presentations",
        "cohort_b_participants",
        "cohort_b_sessions",
    ):
        video_support[column] = (
            video_support[column].fillna(0).astype(int)
        )

    video_support["presentations_removed"] = (
        video_support["full_presentations"]
        - video_support["cohort_b_presentations"]
    )
    video_support["participants_removed"] = (
        video_support["full_participants"]
        - video_support["cohort_b_participants"]
    )
    video_support["lost_from_cohort_b"] = (
        video_support["cohort_b_presentations"] == 0
    )
    video_support["singleton_participant_in_cohort_b"] = (
        video_support["cohort_b_participants"] == 1
    )
    video_support["at_least_two_participants_in_cohort_b"] = (
        video_support["cohort_b_participants"] >= 2
    )
    video_support = video_support.sort_values(
        ["cohort_b_participants", "video_name"]
    )

    session_manifest_path = (
        manifests_dir / "dejavu_cohort_b_sessions.csv"
    )
    presentation_manifest_path = (
        manifests_dir / "dejavu_cohort_b_presentations.csv"
    )
    emotional_manifest_path = (
        manifests_dir
        / "dejavu_cohort_b_emotional_presentations.csv"
    )
    transition_manifest_path = (
        manifests_dir / "dejavu_cohort_b_transitions.csv"
    )
    video_support_path = (
        docs_dir / "dejavu_cohort_b_video_support.csv"
    )

    sessions.to_csv(session_manifest_path, index=False)
    cohort_presentations.to_csv(
        presentation_manifest_path, index=False
    )
    cohort_emotional.to_csv(
        emotional_manifest_path, index=False
    )
    cohort_transitions.to_csv(
        transition_manifest_path, index=False
    )
    video_support.to_csv(video_support_path, index=False)

    participants = int(
        cohort_presentations["participant_id"].nunique()
    )
    session_count = int(len(included_sessions))
    two_session_participants = int(
        sessions.loc[
            sessions["include_in_cohort_b"]
        ]
        .groupby("participant_id")["session_id"]
        .nunique()
        .eq(2)
        .sum()
    )

    acceptance_checks = {
        "excluded_sessions_match_expected": (
            excluded_sessions == EXPECTED_EXCLUDED
        ),
        "participants_equal_24": participants == 24,
        "sessions_equal_30": session_count == 30,
        "presentations_equal_120": len(cohort_presentations) == 120,
        "emotional_presentations_equal_90": (
            len(cohort_emotional) == 90
        ),
        "baseline_presentations_equal_30": (
            len(cohort_baseline) == 30
        ),
        "transitions_equal_90": len(cohort_transitions) == 90,
        "all_retained_presentations_strict": bool(
            cohort_presentations[
                "strict_two_channel_emg_eligible"
            ].all()
        ),
        "all_retained_transitions_strict": bool(
            cohort_transitions[
                "strict_two_channel_emg_eligible"
            ].all()
        ),
        "no_excluded_session_in_presentation_manifest": not bool(
            set(
                cohort_presentations[
                    "participant_session_key"
                ]
            )
            & excluded_sessions
        ),
        "no_excluded_session_in_transition_manifest": not bool(
            set(cohort_transitions["participant_session_key"])
            & excluded_sessions
        ),
    }
    accepted = all(acceptance_checks.values())

    summary = {
        "generated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "cohort_name": "Cohort_B_Paired_EEG_EMG_Strict",
        "definition": (
            "Retain complete participant-sessions only when all "
            "4 presentations and all 3 transitions pass strict "
            "two-channel raw-EMG QC."
        ),
        "accepted": accepted,
        "acceptance_checks": acceptance_checks,
        "participants": participants,
        "participant_sessions": session_count,
        "two_session_participants": two_session_participants,
        "presentations": int(len(cohort_presentations)),
        "emotional_presentations": int(len(cohort_emotional)),
        "baseline_presentations": int(len(cohort_baseline)),
        "transitions": int(len(cohort_transitions)),
        "included_sessions": sorted(included_sessions),
        "excluded_sessions": sorted(excluded_sessions),
        "expected_excluded_sessions": sorted(EXPECTED_EXCLUDED),
        "unique_emotional_videos_full": int(
            full_emotional["video_name"].nunique()
        ),
        "unique_emotional_videos_cohort_b": int(
            cohort_emotional["video_name"].nunique()
        ),
        "videos_lost_from_cohort_b": sorted(
            video_support.loc[
                video_support["lost_from_cohort_b"],
                "video_name",
            ].astype(str)
        ),
        "singleton_participant_videos_in_cohort_b": sorted(
            video_support.loc[
                video_support[
                    "singleton_participant_in_cohort_b"
                ],
                "video_name",
            ].astype(str)
        ),
        "videos_with_at_least_two_participants_in_cohort_b": int(
            video_support[
                "at_least_two_participants_in_cohort_b"
            ].sum()
        ),
        "cohort_b_video_participant_support_min": int(
            video_support.loc[
                ~video_support["lost_from_cohort_b"],
                "cohort_b_participants",
            ].min()
        ),
        "cohort_b_video_participant_support_median": float(
            video_support.loc[
                ~video_support["lost_from_cohort_b"],
                "cohort_b_participants",
            ].median()
        ),
        "cohort_b_video_participant_support_max": int(
            video_support["cohort_b_participants"].max()
        ),
        "source_manifests": [
            str(source_presentations_path),
            str(source_transitions_path),
        ],
        "output_manifests": [
            str(session_manifest_path),
            str(presentation_manifest_path),
            str(emotional_manifest_path),
            str(transition_manifest_path),
        ],
    }

    json_path = docs_dir / "dejavu_cohort_b_definition.json"
    json_path.write_text(
        json.dumps(
            json_safe(summary),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    report_path = docs_dir / "dejavu_cohort_b_definition.md"
    lines = [
        "# DEJA-VU Cohort B — Paired EEG+EMG Strict",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        "## Cohort rule",
        "",
        "A participant-session is retained only when all four "
        "stimulus-presentation intervals and all three transition "
        "intervals pass strict two-channel raw-EMG QC. The EEG and "
        "EMG rows are then retained or excluded together at the "
        "whole-session level.",
        "",
        "No raw file was deleted or modified. Exclusion is "
        "manifest-based.",
        "",
        "## Final capacity",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Independent participants | {participants} |",
        f"| Participant-sessions | {session_count} |",
        f"| Participants with two retained sessions | "
        f"{two_session_participants} |",
        f"| All presentations | {len(cohort_presentations)} |",
        f"| Emotional presentations | {len(cohort_emotional)} |",
        f"| Baseline presentations | {len(cohort_baseline)} |",
        f"| Transition intervals | {len(cohort_transitions)} |",
        f"| Unique emotional videos | "
        f"{summary['unique_emotional_videos_cohort_b']} |",
        "",
        "## Excluded participant-sessions",
        "",
        "| Participant-session | Reason |",
        "|---|---|",
    ]
    for _, row in sessions.loc[
        ~sessions["include_in_cohort_b"]
    ].iterrows():
        lines.append(
            f"| {row['participant_session_key']} | "
            f"{row['exclusion_reason']} |"
        )

    lines.extend(
        [
            "",
            "## Video-support impact",
            "",
            f"- Emotional videos before strict exclusion: "
            f"`{summary['unique_emotional_videos_full']}`",
            f"- Emotional videos after strict exclusion: "
            f"`{summary['unique_emotional_videos_cohort_b']}`",
            f"- Videos lost entirely: "
            f"`{', '.join(summary['videos_lost_from_cohort_b']) or 'None'}`",
            f"- Videos represented by only one participant: "
            f"`{', '.join(summary['singleton_participant_videos_in_cohort_b']) or 'None'}`",
            f"- Videos with at least two participants: "
            f"`{summary['videos_with_at_least_two_participants_in_cohort_b']}`",
            f"- Participant support per retained video: "
            f"min `{summary['cohort_b_video_participant_support_min']}`, "
            f"median `{summary['cohort_b_video_participant_support_median']}`, "
            f"max `{summary['cohort_b_video_participant_support_max']}`",
            "",
            "## Acceptance checks",
            "",
            "| Check | Result |",
            "|---|---|",
        ]
    )
    for check, result in acceptance_checks.items():
        lines.append(
            f"| `{check}` | {'PASS' if result else 'FAIL'} |"
        )

    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "**Cohort B accepted and ready for label-policy "
                "capacity audit.**"
                if accepted
                else "**Cohort B NOT accepted; inspect failed checks.**"
            ),
            "",
            "## Outputs",
            "",
            "- `manifests/dejavu_cohort_b_sessions.csv`",
            "- `manifests/dejavu_cohort_b_presentations.csv`",
            "- `manifests/dejavu_cohort_b_emotional_presentations.csv`",
            "- `manifests/dejavu_cohort_b_transitions.csv`",
            "- `docs/dejavu_cohort_b_video_support.csv`",
            "- `docs/dejavu_cohort_b_definition.json`",
            "",
        ]
    )
    report_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    print("\nDEJA-VU COHORT B CHECKPOINT")
    print(f"Accepted: {accepted}")
    print(f"Participants: {participants}")
    print(f"Participant-sessions: {session_count}")
    print(f"Presentations: {len(cohort_presentations)}")
    print(f"Emotional presentations: {len(cohort_emotional)}")
    print(f"Transitions: {len(cohort_transitions)}")
    print(
        "Excluded sessions: "
        + ", ".join(sorted(excluded_sessions))
    )
    print(
        "Unique emotional videos: "
        f"{summary['unique_emotional_videos_cohort_b']}"
    )
    print(
        "Videos lost entirely: "
        + (
            ", ".join(summary["videos_lost_from_cohort_b"])
            or "None"
        )
    )
    print(f"Report: {report_path}")

    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())

