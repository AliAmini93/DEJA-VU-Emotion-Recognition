#!/usr/bin/env python3
"""Refine DEJA-VU raw-EMG eligibility with saturation and plateau checks.

Read-only against raw XDF and existing manifests. It re-inspects only sessions
already implicated by event-level or session-level EMG QC. It does not modify
source manifests or dataset files.
"""
from __future__ import annotations

import argparse
import gc
import json
import math
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyxdf


SUBJECT_RE = re.compile(r"^sub-(P\d+)$", re.IGNORECASE)
SESSION_RE = re.compile(r"^ses-(S\d+)$", re.IGNORECASE)
TRUE_EMG_RE = re.compile(r"(^|_)EMG_CH([12])(_|$)", re.IGNORECASE)


class AuditError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--min-finite-fraction", type=float, default=0.999)
    p.add_argument("--fail-mode-fraction", type=float, default=0.95)
    p.add_argument("--fail-longest-run-fraction", type=float, default=0.50)
    p.add_argument("--warn-mode-fraction", type=float, default=0.20)
    p.add_argument("--warn-longest-run-fraction", type=float, default=0.10)
    return p.parse_args()


def unwrap(value: Any, default: str = "") -> str:
    cur = value
    while isinstance(cur, (list, tuple)):
        if not cur:
            return default
        cur = cur[0]
    return default if cur is None else str(cur)


def stream_name(stream: dict[str, Any]) -> str:
    return unwrap(stream.get("info", {}).get("name"), "")


def stream_type(stream: dict[str, Any]) -> str:
    return unwrap(stream.get("info", {}).get("type"), "")


def channel_metadata(stream: dict[str, Any]) -> list[dict[str, str]]:
    try:
        desc = stream["info"]["desc"][0]
        channels = desc["channels"][0]["channel"]
        if isinstance(channels, dict):
            channels = [channels]
    except (KeyError, IndexError, TypeError):
        channels = []
    result = []
    for idx, ch in enumerate(channels or []):
        if not isinstance(ch, dict):
            ch = {}
        result.append(
            {
                "index": str(idx),
                "label": unwrap(ch.get("label"), f"channel_{idx}"),
                "unit": unwrap(ch.get("unit"), ""),
            }
        )
    return result


def parse_path_identity(path: Path) -> tuple[str, str]:
    participant = ""
    session = ""
    for part in path.parts:
        m = SUBJECT_RE.match(part)
        if m:
            participant = m.group(1).upper()
        m = SESSION_RE.match(part)
        if m:
            session = m.group(1).upper()
    if not participant or not session:
        raise AuditError(f"Cannot parse participant/session from {path}")
    return participant, session


def find_eeg_stream(streams: list[dict[str, Any]]) -> dict[str, Any]:
    exact = [s for s in streams if stream_name(s).upper() == "DSI_FLEX"]
    if len(exact) == 1:
        return exact[0]
    typed = [s for s in streams if stream_type(s).upper() == "EEG"]
    if len(typed) == 1:
        return typed[0]
    raise AuditError(f"EEG stream not unique: exact={len(exact)}, typed={len(typed)}")


def true_emg_indices(labels: list[str]) -> list[int]:
    hits: list[tuple[int, int]] = []
    for idx, label in enumerate(labels):
        upper = label.upper()
        if "STATUS" in upper or "BATTERY" in upper:
            continue
        match = TRUE_EMG_RE.search(upper)
        if match:
            hits.append((int(match.group(2)), idx))
    hits.sort()
    return [idx for _, idx in hits]


def find_emg_stream(
    streams: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[int], list[dict[str, str]]]:
    candidates = []
    for stream in streams:
        meta = channel_metadata(stream)
        indices = true_emg_indices([x["label"] for x in meta])
        if len(indices) >= 2:
            candidates.append((stream, indices[:2], meta))
    exact = [x for x in candidates if stream_name(x[0]).upper() == "SHIMMER_BBBD"]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    raise AuditError(
        "Descriptor-confirmed EMG stream not unique: "
        + ",".join(stream_name(x[0]) for x in candidates)
    )


def longest_equal_run(values: np.ndarray) -> int:
    if values.size == 0:
        return 0
    if values.size == 1:
        return 1
    change_points = np.flatnonzero(np.diff(values) != 0) + 1
    boundaries = np.concatenate(([0], change_points, [values.size]))
    return int(np.max(np.diff(boundaries)))


def event_channel_metrics(values: np.ndarray) -> dict[str, Any]:
    x = np.asarray(values, dtype=np.float64).reshape(-1)
    finite_mask = np.isfinite(x)
    finite = x[finite_mask]
    n = int(x.size)
    finite_n = int(finite.size)
    finite_fraction = float(finite_n / n) if n else 0.0

    if finite_n == 0:
        return {
            "sample_count": n,
            "finite_count": 0,
            "finite_fraction": 0.0,
            "nan_count": int(np.isnan(x).sum()),
            "mean": None,
            "std": None,
            "minimum": None,
            "maximum": None,
            "robust_range_p01_p99": None,
            "unique_count": 0,
            "unique_fraction": 0.0,
            "mode_value": None,
            "mode_fraction": None,
            "longest_equal_run": 0,
            "longest_equal_run_fraction": None,
            "endpoint_fraction": None,
            "exact_flatline": False,
        }

    unique, counts = np.unique(finite, return_counts=True)
    mode_idx = int(np.argmax(counts))
    mode_value = float(unique[mode_idx])
    mode_fraction = float(counts[mode_idx] / finite_n)
    longest = longest_equal_run(finite)
    minimum = float(np.min(finite))
    maximum = float(np.max(finite))
    p01, p99 = np.quantile(finite, [0.01, 0.99])
    robust_range = float(p99 - p01)
    endpoint_fraction = float(
        ((finite == minimum) | (finite == maximum)).sum() / finite_n
    )
    std = float(np.std(finite))
    exact_flatline = bool(
        unique.size <= 1 or std == 0.0 or robust_range == 0.0
    )

    return {
        "sample_count": n,
        "finite_count": finite_n,
        "finite_fraction": finite_fraction,
        "nan_count": int(np.isnan(x).sum()),
        "mean": float(np.mean(finite)),
        "std": std,
        "minimum": minimum,
        "maximum": maximum,
        "robust_range_p01_p99": robust_range,
        "unique_count": int(unique.size),
        "unique_fraction": float(unique.size / finite_n),
        "mode_value": mode_value,
        "mode_fraction": mode_fraction,
        "longest_equal_run": longest,
        "longest_equal_run_fraction": float(longest / finite_n),
        "endpoint_fraction": endpoint_fraction,
        "exact_flatline": exact_flatline,
    }


def classify_channel(
    metrics: dict[str, Any],
    min_finite_fraction: float,
    fail_mode_fraction: float,
    fail_longest_run_fraction: float,
    warn_mode_fraction: float,
    warn_longest_run_fraction: float,
) -> tuple[str, str]:
    fail: list[str] = []
    warn: list[str] = []

    if metrics["sample_count"] == 0:
        fail.append("NO_SAMPLES")
    if metrics["finite_fraction"] < min_finite_fraction:
        fail.append("NONFINITE")
    if metrics["exact_flatline"]:
        fail.append("FLATLINE")
    mode_fraction = metrics["mode_fraction"]
    run_fraction = metrics["longest_equal_run_fraction"]
    if mode_fraction is not None and mode_fraction >= fail_mode_fraction:
        fail.append("SATURATED_MODE")
    if run_fraction is not None and run_fraction >= fail_longest_run_fraction:
        fail.append("LONG_PLATEAU")

    if not fail:
        if mode_fraction is not None and mode_fraction >= warn_mode_fraction:
            warn.append("HIGH_MODE_FRACTION")
        if run_fraction is not None and run_fraction >= warn_longest_run_fraction:
            warn.append("LONG_RUN_WARNING")

    if fail:
        return "FAIL", ";".join(dict.fromkeys(fail))
    if warn:
        return "WARN", ";".join(dict.fromkeys(warn))
    return "PASS", "PASS"


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


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    raw_root = data_root / "extracted" / "dataset" / "DEJA-VU" / "raw"
    docs = repo_root / "docs"
    manifests = repo_root / "manifests"

    session_path = docs / "dejavu_raw_emg_eligibility_by_session.csv"
    presentation_path = manifests / "dejavu_stimulus_presentation_emg_eligibility.csv"
    transition_path = manifests / "dejavu_transition_emg_eligibility.csv"
    for path in (session_path, presentation_path, transition_path):
        if not path.exists():
            raise AuditError(f"Required input missing: {path}")

    session_df = pd.read_csv(session_path)
    presentations = pd.read_csv(presentation_path)
    transitions = pd.read_csv(transition_path)

    implicated = set(
        session_df.loc[
            session_df["session_status"].astype(str) != "PASS",
            "participant_session_key",
        ].astype(str)
    )
    implicated.update(
        presentations.loc[
            ~presentations["raw_emg_two_channel_eligible"].astype(bool),
            "participant_session_key",
        ].astype(str)
    )
    implicated.update(
        transitions.loc[
            ~transitions["raw_emg_two_channel_eligible"].astype(bool),
            "participant_session_key",
        ].astype(str)
    )
    implicated = sorted(implicated)

    print("Implicated sessions:", ", ".join(implicated))
    xdf_lookup: dict[str, Path] = {}
    for path in sorted(raw_root.glob("sub-*/ses-*/eeg/*.xdf")):
        participant, session = parse_path_identity(path)
        xdf_lookup[f"{participant}_{session}"] = path

    event_rows: list[dict[str, Any]] = []
    hard_errors: list[str] = []

    for number, key in enumerate(implicated, start=1):
        print(f"[{number:02d}/{len(implicated):02d}] {key}", flush=True)
        xdf_path = xdf_lookup.get(key)
        if xdf_path is None:
            hard_errors.append(f"{key}:XDF_NOT_FOUND")
            continue

        try:
            streams, _ = pyxdf.load_xdf(str(xdf_path), verbose=False)
            eeg = find_eeg_stream(streams)
            emg, indices, meta = find_emg_stream(streams)
            values = np.asarray(emg["time_series"], dtype=np.float64)
            timestamps = np.asarray(emg["time_stamps"], dtype=np.float64)
            eeg_ts = np.asarray(eeg["time_stamps"], dtype=np.float64)
            if values.ndim != 2 or values.shape[0] != timestamps.size:
                raise AuditError(
                    f"EMG shape mismatch: values={values.shape}, timestamps={timestamps.shape}"
                )
            if len(indices) != 2:
                raise AuditError(f"Expected two true EMG indices, got {indices}")
            finite_eeg = eeg_ts[np.isfinite(eeg_ts)]
            if finite_eeg.size == 0:
                raise AuditError("No finite EEG timestamps")
            relative_ts = timestamps - float(finite_eeg[0])
            participant, session = key.split("_", 1)

            units: list[tuple[str, pd.DataFrame, str, str]] = [
                (
                    "presentation",
                    presentations[
                        presentations["participant_session_key"].astype(str) == key
                    ],
                    "timeline_start_sec",
                    "timeline_end_sec",
                ),
                (
                    "transition",
                    transitions[
                        transitions["participant_session_key"].astype(str) == key
                    ],
                    "transition_start_sec",
                    "transition_end_sec",
                ),
            ]

            for unit_type, frame, start_col, end_col in units:
                for _, row in frame.iterrows():
                    start = float(row[start_col])
                    end = float(row[end_col])
                    mask = (
                        np.isfinite(relative_ts)
                        & (relative_ts >= start)
                        & (relative_ts <= end)
                    )
                    selected = values[mask][:, indices] if mask.any() else np.empty((0, 2))

                    if unit_type == "presentation":
                        unit_id = str(row["presentation_id"])
                    else:
                        unit_id = (
                            f"{row['participant_id']}_{row['session_id']}"
                            f"_t{int(row['transition_position'])}"
                        )

                    channel_results = []
                    for logical_idx in range(2):
                        metrics = event_channel_metrics(selected[:, logical_idx])
                        status, reason = classify_channel(
                            metrics,
                            args.min_finite_fraction,
                            args.fail_mode_fraction,
                            args.fail_longest_run_fraction,
                            args.warn_mode_fraction,
                            args.warn_longest_run_fraction,
                        )
                        channel_results.append((metrics, status, reason))

                    prior_two = bool(row["raw_emg_two_channel_eligible"])
                    prior_one = bool(row["raw_emg_one_channel_eligible"])
                    statuses = [x[1] for x in channel_results]
                    strict_two = bool(prior_two and all(s != "FAIL" for s in statuses))
                    strict_one = bool(prior_one and any(s != "FAIL" for s in statuses))

                    base = {
                        "unit_type": unit_type,
                        "unit_id": unit_id,
                        "participant_id": participant,
                        "session_id": session,
                        "participant_session_key": key,
                        "start_sec": start,
                        "end_sec": end,
                        "duration_sec": end - start,
                        "prior_two_channel_eligible": prior_two,
                        "prior_one_channel_eligible": prior_one,
                        "strict_two_channel_eligible": strict_two,
                        "strict_one_channel_eligible": strict_one,
                        "strict_event_status": (
                            "PASS"
                            if strict_two
                            else "ONE_CHANNEL_ONLY"
                            if strict_one
                            else "FAIL"
                        ),
                        "true_emg_channel_1_index": indices[0],
                        "true_emg_channel_1_label": meta[indices[0]]["label"],
                        "true_emg_channel_2_index": indices[1],
                        "true_emg_channel_2_label": meta[indices[1]]["label"],
                    }
                    for logical_idx, (metrics, status, reason) in enumerate(
                        channel_results, start=1
                    ):
                        base[f"ch{logical_idx}_status"] = status
                        base[f"ch{logical_idx}_reason"] = reason
                        for metric_name, metric_value in metrics.items():
                            base[f"ch{logical_idx}_{metric_name}"] = metric_value
                    event_rows.append(base)

        except Exception as exc:
            traceback.print_exc()
            hard_errors.append(f"{key}:{type(exc).__name__}:{exc}")
        finally:
            try:
                del streams
            except UnboundLocalError:
                pass
            gc.collect()

    events = pd.DataFrame(event_rows).sort_values(
        ["participant_id", "session_id", "unit_type", "start_sec"]
    )
    forensic_csv = docs / "dejavu_raw_emg_strict_signal_qc_events.csv"
    events.to_csv(forensic_csv, index=False)

    revised_presentations = presentations.copy()
    revised_transitions = transitions.copy()

    for target, unit_type, id_builder in (
        (
            revised_presentations,
            "presentation",
            lambda r: str(r["presentation_id"]),
        ),
        (
            revised_transitions,
            "transition",
            lambda r: (
                f"{r['participant_id']}_{r['session_id']}"
                f"_t{int(r['transition_position'])}"
            ),
        ),
    ):
        target["strict_signal_qc_applied"] = False
        target["strict_two_channel_emg_eligible"] = target[
            "raw_emg_two_channel_eligible"
        ].astype(bool)
        target["strict_one_channel_emg_eligible"] = target[
            "raw_emg_one_channel_eligible"
        ].astype(bool)
        target["strict_signal_qc_status"] = "NOT_IMPLICATED"
        if not events.empty:
            subset = events[events["unit_type"] == unit_type].set_index("unit_id")
            for idx, row in target.iterrows():
                unit_id = id_builder(row)
                if unit_id in subset.index:
                    result = subset.loc[unit_id]
                    target.at[idx, "strict_signal_qc_applied"] = True
                    target.at[idx, "strict_two_channel_emg_eligible"] = bool(
                        result["strict_two_channel_eligible"]
                    )
                    target.at[idx, "strict_one_channel_emg_eligible"] = bool(
                        result["strict_one_channel_eligible"]
                    )
                    target.at[idx, "strict_signal_qc_status"] = str(
                        result["strict_event_status"]
                    )

    revised_p_path = (
        manifests / "dejavu_stimulus_presentation_emg_strict_qc.csv"
    )
    revised_t_path = manifests / "dejavu_transition_emg_strict_qc.csv"
    revised_presentations.to_csv(revised_p_path, index=False)
    revised_transitions.to_csv(revised_t_path, index=False)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "implicated_sessions": implicated,
        "hard_errors": hard_errors,
        "thresholds": {
            "min_finite_fraction": args.min_finite_fraction,
            "fail_mode_fraction": args.fail_mode_fraction,
            "fail_longest_run_fraction": args.fail_longest_run_fraction,
            "warn_mode_fraction": args.warn_mode_fraction,
            "warn_longest_run_fraction": args.warn_longest_run_fraction,
        },
        "presentation_total": int(len(revised_presentations)),
        "presentation_prior_two_channel_eligible": int(
            revised_presentations["raw_emg_two_channel_eligible"].sum()
        ),
        "presentation_strict_two_channel_eligible": int(
            revised_presentations["strict_two_channel_emg_eligible"].sum()
        ),
        "presentation_prior_one_channel_eligible": int(
            revised_presentations["raw_emg_one_channel_eligible"].sum()
        ),
        "presentation_strict_one_channel_eligible": int(
            revised_presentations["strict_one_channel_emg_eligible"].sum()
        ),
        "transition_total": int(len(revised_transitions)),
        "transition_prior_two_channel_eligible": int(
            revised_transitions["raw_emg_two_channel_eligible"].sum()
        ),
        "transition_strict_two_channel_eligible": int(
            revised_transitions["strict_two_channel_emg_eligible"].sum()
        ),
        "transition_prior_one_channel_eligible": int(
            revised_transitions["raw_emg_one_channel_eligible"].sum()
        ),
        "transition_strict_one_channel_eligible": int(
            revised_transitions["strict_one_channel_emg_eligible"].sum()
        ),
        "event_status_counts": events["strict_event_status"].value_counts().to_dict()
        if not events.empty
        else {},
        "channel_status_counts": {
            "ch1": events["ch1_status"].value_counts().to_dict()
            if not events.empty
            else {},
            "ch2": events["ch2_status"].value_counts().to_dict()
            if not events.empty
            else {},
        },
    }

    json_path = docs / "dejavu_raw_emg_strict_signal_qc.json"
    json_path.write_text(
        json.dumps(json_safe(summary), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = docs / "dejavu_raw_emg_strict_signal_qc.md"
    failed_events = events[events["strict_event_status"] != "PASS"]
    lines = [
        "# DEJA-VU Raw EMG Strict Signal-QC Refinement",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        "This refinement adds saturation and long-plateau checks to the previous coverage/finite/flatline audit. "
        "Only sessions implicated by the earlier audit were reread from raw XDF.",
        "",
        "## Revised capacity",
        "",
        "| Unit | Total | Previous two-channel | Strict two-channel | Previous one-channel | Strict one-channel |",
        "|---|---:|---:|---:|---:|---:|",
        f"| Presentations | {summary['presentation_total']} | {summary['presentation_prior_two_channel_eligible']} | {summary['presentation_strict_two_channel_eligible']} | {summary['presentation_prior_one_channel_eligible']} | {summary['presentation_strict_one_channel_eligible']} |",
        f"| Transitions | {summary['transition_total']} | {summary['transition_prior_two_channel_eligible']} | {summary['transition_strict_two_channel_eligible']} | {summary['transition_prior_one_channel_eligible']} | {summary['transition_strict_one_channel_eligible']} |",
        "",
        "## Failure rules",
        "",
        f"- finite fraction below `{args.min_finite_fraction}`",
        "- exact flatline",
        f"- one exact value occupies at least `{args.fail_mode_fraction:.0%}` of finite samples",
        f"- one uninterrupted equal-value run occupies at least `{args.fail_longest_run_fraction:.0%}` of finite samples",
        "",
        "These are deterministic engineering-QC rules, not performance-selected thresholds.",
        "",
        "## Non-passing implicated events",
        "",
        "| Type | Unit | Session | Status | CH1 | CH2 |",
        "|---|---|---|---|---|---|",
    ]
    for _, row in failed_events.iterrows():
        lines.append(
            f"| {row['unit_type']} | {row['unit_id']} | {row['participant_session_key']} | "
            f"{row['strict_event_status']} | {row['ch1_status']}:{row['ch1_reason']} | "
            f"{row['ch2_status']}:{row['ch2_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Decision boundary",
            "",
            "- `strict_two_channel_emg_eligible=True` is the candidate requirement for standard two-channel EMG and paired EEG+EMG experiments.",
            "- `strict_one_channel_emg_eligible=True` remains diagnostic only. A one-channel fallback is not authorized by this report.",
            "- The official distributed EMG HDF5 groups remain unusable; future EMG must be re-derived from raw XDF indices identified by channel descriptors.",
            "",
            "## Outputs",
            "",
            "- `docs/dejavu_raw_emg_strict_signal_qc_events.csv`",
            "- `docs/dejavu_raw_emg_strict_signal_qc.json`",
            "- `manifests/dejavu_stimulus_presentation_emg_strict_qc.csv`",
            "- `manifests/dejavu_transition_emg_strict_qc.csv`",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nDEJA-VU STRICT EMG SIGNAL-QC CHECKPOINT")
    print(
        "Presentations strict two-channel: "
        f"{summary['presentation_strict_two_channel_eligible']}/{summary['presentation_total']}"
    )
    print(
        "Presentations strict one-channel: "
        f"{summary['presentation_strict_one_channel_eligible']}/{summary['presentation_total']}"
    )
    print(
        "Transitions strict two-channel: "
        f"{summary['transition_strict_two_channel_eligible']}/{summary['transition_total']}"
    )
    print(
        "Transitions strict one-channel: "
        f"{summary['transition_strict_one_channel_eligible']}/{summary['transition_total']}"
    )
    print(f"Report: {report_path}")
    return 1 if hard_errors else 0


if __name__ == "__main__":
    sys.exit(main())

