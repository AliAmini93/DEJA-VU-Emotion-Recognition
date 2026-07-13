#!/usr/bin/env python3
"""Build event-level raw-EMG integrity and EEG+EMG eligibility manifests.

Read-only against DEJA-VU raw XDF files. Existing manifests are not modified.
The script resolves true EMG channels from XDF descriptors, audits every
presentation and transition interval, and writes repository-safe reports.
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
    p.add_argument("--coverage-tolerance-sec", type=float, default=1.0)
    p.add_argument("--minimum-sample-ratio", type=float, default=0.98)
    p.add_argument("--minimum-finite-fraction", type=float, default=0.999)
    return p.parse_args()


def unwrap(value: Any, default: str = "") -> str:
    current = value
    while isinstance(current, (list, tuple)):
        if not current:
            return default
        current = current[0]
    return default if current is None else str(current)


def stream_name(stream: dict[str, Any]) -> str:
    return unwrap(stream.get("info", {}).get("name"), "")


def stream_type(stream: dict[str, Any]) -> str:
    return unwrap(stream.get("info", {}).get("type"), "")


def float_or_none(value: Any) -> float | None:
    try:
        x = float(unwrap(value))
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def channel_metadata(stream: dict[str, Any]) -> list[dict[str, str]]:
    info = stream.get("info", {})
    try:
        desc = info.get("desc", [])
        d0 = desc[0] if desc else {}
        channels = d0.get("channels", [])
        c0 = channels[0] if channels else {}
        items = c0.get("channel", [])
        if isinstance(items, dict):
            items = [items]
    except (AttributeError, IndexError, TypeError):
        items = []

    result: list[dict[str, str]] = []
    for index, item in enumerate(items or []):
        if not isinstance(item, dict):
            item = {}
        result.append(
            {
                "index": str(index),
                "label": unwrap(item.get("label"), f"channel_{index}"),
                "unit": unwrap(item.get("unit"), ""),
            }
        )
    return result


def parse_path_identity(path: Path) -> tuple[str, str]:
    participant = ""
    session = ""
    for part in path.parts:
        ms = SUBJECT_RE.match(part)
        if ms:
            participant = ms.group(1).upper()
        me = SESSION_RE.match(part)
        if me:
            session = me.group(1).upper()
    if not participant or not session:
        raise AuditError(f"Cannot parse identity from {path}")
    return participant, session


def filename_identity(path: Path) -> tuple[str, str] | None:
    m = re.search(r"sub-(P\d+)_ses-(S\d+)", path.name, flags=re.IGNORECASE)
    return (m.group(1).upper(), m.group(2).upper()) if m else None


def find_eeg_stream(streams: list[dict[str, Any]]) -> dict[str, Any]:
    exact = [s for s in streams if stream_name(s).upper() == "DSI_FLEX"]
    if len(exact) == 1:
        return exact[0]
    typed = [s for s in streams if stream_type(s).upper() == "EEG"]
    if len(typed) == 1:
        return typed[0]
    raise AuditError(f"EEG stream is not unique: exact={len(exact)}, typed={len(typed)}")


def true_emg_indices(labels: list[str]) -> list[int]:
    matched: list[tuple[int, int]] = []
    for idx, label in enumerate(labels):
        upper = label.upper()
        if "STATUS" in upper or "BATTERY" in upper:
            continue
        m = TRUE_EMG_RE.search(upper)
        if m:
            matched.append((int(m.group(2)), idx))
    matched.sort()
    return [idx for _, idx in matched]


def find_emg_stream(
    streams: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[int], list[dict[str, str]]]:
    candidates = []
    for stream in streams:
        meta = channel_metadata(stream)
        labels = [x["label"] for x in meta]
        indices = true_emg_indices(labels)
        if len(indices) >= 2:
            candidates.append((stream, indices[:2], meta))
    exact = [x for x in candidates if stream_name(x[0]).upper() == "SHIMMER_BBBD"]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    raise AuditError(
        "Descriptor-confirmed EMG stream is not unique: "
        + ",".join(stream_name(x[0]) for x in candidates)
    )


def as_numeric_2d(values: Any) -> np.ndarray:
    arr = np.asarray(values)
    if arr.ndim == 1:
        arr = arr[:, None]
    if arr.ndim != 2:
        raise AuditError(f"Expected 2-D signal array, got {arr.shape}")
    return arr.astype(np.float64, copy=False)


def longest_equal_run(values: np.ndarray) -> int:
    """Longest exact repeated-value run among finite values."""
    if values.size == 0:
        return 0
    if values.size == 1:
        return 1
    changes = np.flatnonzero(np.diff(values) != 0) + 1
    bounds = np.concatenate(([0], changes, [values.size]))
    return int(np.max(np.diff(bounds)))


def signal_metrics(values: np.ndarray) -> dict[str, Any]:
    x = np.asarray(values, dtype=np.float64).reshape(-1)
    finite_mask = np.isfinite(x)
    finite = x[finite_mask]
    sample_count = int(x.size)
    finite_count = int(finite.size)
    finite_fraction = float(finite_count / sample_count) if sample_count else 0.0

    if finite_count:
        mean = float(np.mean(finite))
        std = float(np.std(finite))
        median = float(np.median(finite))
        mad = float(np.median(np.abs(finite - median)))
        minimum = float(np.min(finite))
        maximum = float(np.max(finite))
        p01, p99 = np.quantile(finite, [0.01, 0.99])
        robust_range = float(p99 - p01)
        unique_count = int(np.unique(finite).size)
        longest_run = longest_equal_run(finite)
        extreme_fraction = float(
            ((finite == minimum) | (finite == maximum)).sum() / finite_count
        )
    else:
        mean = std = median = mad = minimum = maximum = robust_range = None
        unique_count = 0
        longest_run = 0
        extreme_fraction = None

    exact_flatline = bool(
        finite_count > 0 and (unique_count <= 1 or robust_range == 0.0 or std == 0.0)
    )
    low_variability_warning = bool(
        finite_count > 0
        and not exact_flatline
        and (
            unique_count < 10
            or (
                robust_range is not None
                and robust_range <= np.finfo(np.float64).eps
                * max(abs(median or 0.0), 1.0)
                * 100
            )
        )
    )

    return {
        "sample_count": sample_count,
        "finite_count": finite_count,
        "nan_count": int(np.isnan(x).sum()),
        "posinf_count": int(np.isposinf(x).sum()),
        "neginf_count": int(np.isneginf(x).sum()),
        "finite_fraction": finite_fraction,
        "mean": mean,
        "std": std,
        "median": median,
        "mad": mad,
        "minimum": minimum,
        "maximum": maximum,
        "robust_range_p01_p99": robust_range,
        "unique_count": unique_count,
        "longest_equal_run": longest_run,
        "longest_equal_run_fraction": float(longest_run / finite_count)
        if finite_count
        else None,
        "extreme_value_fraction": extreme_fraction,
        "exact_flatline": exact_flatline,
        "low_variability_warning": low_variability_warning,
    }


def timestamp_metrics(timestamps: Any) -> dict[str, Any]:
    ts = np.asarray(timestamps, dtype=np.float64).reshape(-1)
    finite = ts[np.isfinite(ts)]
    if finite.size == 0:
        return {
            "sample_count": int(ts.size),
            "start": None,
            "end": None,
            "duration": None,
            "median_gap": None,
            "max_gap": None,
            "effective_rate": None,
            "monotonic": False,
            "nonfinite": int((~np.isfinite(ts)).sum()),
        }
    diffs = np.diff(finite)
    positive = diffs[diffs > 0]
    median_gap = float(np.median(positive)) if positive.size else None
    return {
        "sample_count": int(ts.size),
        "start": float(finite[0]),
        "end": float(finite[-1]),
        "duration": float(finite[-1] - finite[0]) if finite.size >= 2 else 0.0,
        "median_gap": median_gap,
        "max_gap": float(np.max(positive)) if positive.size else None,
        "effective_rate": 1.0 / median_gap if median_gap and median_gap > 0 else None,
        "monotonic": bool(np.all(diffs >= 0)) if diffs.size else True,
        "nonfinite": int((~np.isfinite(ts)).sum()),
    }


def interval_metrics(
    relative_ts: np.ndarray,
    emg_values: np.ndarray,
    true_indices: list[int],
    start_sec: float,
    end_sec: float,
    nominal_rate: float | None,
    tolerance_sec: float,
    min_sample_ratio: float,
    min_finite_fraction: float,
) -> dict[str, Any]:
    if not math.isfinite(start_sec) or not math.isfinite(end_sec) or end_sec <= start_sec:
        return {
            "raw_emg_boundary_covered": False,
            "raw_emg_observed_samples": 0,
            "raw_emg_expected_samples": None,
            "raw_emg_sample_coverage_ratio": None,
            "raw_emg_max_gap_sec": None,
            "raw_emg_gap_ok": False,
            "emg_ch1_finite_fraction": None,
            "emg_ch2_finite_fraction": None,
            "emg_ch1_exact_flatline": None,
            "emg_ch2_exact_flatline": None,
            "emg_ch1_low_variability_warning": None,
            "emg_ch2_low_variability_warning": None,
            "raw_emg_two_channel_eligible": False,
            "raw_emg_one_channel_eligible": False,
            "raw_emg_eligibility_reason": "INVALID_INTERVAL",
        }

    finite_ts = relative_ts[np.isfinite(relative_ts)]
    if finite_ts.size == 0:
        return {
            "raw_emg_boundary_covered": False,
            "raw_emg_observed_samples": 0,
            "raw_emg_expected_samples": None,
            "raw_emg_sample_coverage_ratio": 0.0,
            "raw_emg_max_gap_sec": None,
            "raw_emg_gap_ok": False,
            "emg_ch1_finite_fraction": 0.0,
            "emg_ch2_finite_fraction": 0.0,
            "emg_ch1_exact_flatline": None,
            "emg_ch2_exact_flatline": None,
            "emg_ch1_low_variability_warning": None,
            "emg_ch2_low_variability_warning": None,
            "raw_emg_two_channel_eligible": False,
            "raw_emg_one_channel_eligible": False,
            "raw_emg_eligibility_reason": "NO_TIMESTAMPS",
        }

    mask = np.isfinite(relative_ts) & (relative_ts >= start_sec) & (relative_ts <= end_sec)
    selected_ts = relative_ts[mask]
    selected = emg_values[mask][:, true_indices] if mask.any() else np.empty((0, 2))

    boundary = bool(
        finite_ts[0] <= start_sec + tolerance_sec
        and finite_ts[-1] >= end_sec - tolerance_sec
    )
    expected = (
        int(round((end_sec - start_sec) * nominal_rate))
        if nominal_rate and nominal_rate > 0
        else None
    )
    ratio = (
        float(selected_ts.size / expected)
        if expected is not None and expected > 0
        else None
    )

    if selected_ts.size >= 2:
        gaps = np.diff(selected_ts)
        positive = gaps[gaps > 0]
        max_gap = float(np.max(positive)) if positive.size else 0.0
        typical = (
            1.0 / nominal_rate
            if nominal_rate and nominal_rate > 0
            else (float(np.median(positive)) if positive.size else None)
        )
        gap_ok = bool(
            typical is not None
            and max_gap <= max(5.0 * typical, tolerance_sec)
        )
    else:
        max_gap = None
        gap_ok = False

    ch_metrics = [
        signal_metrics(selected[:, idx]) if selected.shape[0] else signal_metrics(np.array([]))
        for idx in range(2)
    ]
    channel_valid = [
        bool(
            selected.shape[0] > 0
            and ch["finite_fraction"] >= min_finite_fraction
            and not ch["exact_flatline"]
        )
        for ch in ch_metrics
    ]
    coverage_ok = bool(
        boundary
        and gap_ok
        and (ratio is None or ratio >= min_sample_ratio)
    )
    two_channel = bool(coverage_ok and all(channel_valid))
    one_channel = bool(coverage_ok and any(channel_valid))

    reasons: list[str] = []
    if not boundary:
        reasons.append("BOUNDARY_NOT_COVERED")
    if not gap_ok:
        reasons.append("GAP_OR_TOO_FEW_SAMPLES")
    if ratio is not None and ratio < min_sample_ratio:
        reasons.append("LOW_SAMPLE_COVERAGE")
    for idx, valid in enumerate(channel_valid, start=1):
        if valid:
            continue
        ch = ch_metrics[idx - 1]
        if ch["finite_fraction"] < min_finite_fraction:
            reasons.append(f"CH{idx}_NONFINITE")
        if ch["exact_flatline"]:
            reasons.append(f"CH{idx}_FLATLINE")
        if ch["sample_count"] == 0:
            reasons.append(f"CH{idx}_NO_SAMPLES")

    return {
        "raw_emg_boundary_covered": boundary,
        "raw_emg_observed_samples": int(selected_ts.size),
        "raw_emg_expected_samples": expected,
        "raw_emg_sample_coverage_ratio": ratio,
        "raw_emg_max_gap_sec": max_gap,
        "raw_emg_gap_ok": gap_ok,
        "emg_ch1_finite_fraction": ch_metrics[0]["finite_fraction"],
        "emg_ch2_finite_fraction": ch_metrics[1]["finite_fraction"],
        "emg_ch1_exact_flatline": ch_metrics[0]["exact_flatline"],
        "emg_ch2_exact_flatline": ch_metrics[1]["exact_flatline"],
        "emg_ch1_low_variability_warning": ch_metrics[0]["low_variability_warning"],
        "emg_ch2_low_variability_warning": ch_metrics[1]["low_variability_warning"],
        "emg_ch1_std": ch_metrics[0]["std"],
        "emg_ch2_std": ch_metrics[1]["std"],
        "emg_ch1_robust_range": ch_metrics[0]["robust_range_p01_p99"],
        "emg_ch2_robust_range": ch_metrics[1]["robust_range_p01_p99"],
        "raw_emg_two_channel_eligible": two_channel,
        "raw_emg_one_channel_eligible": one_channel,
        "raw_emg_eligibility_reason": "PASS" if two_channel else ";".join(dict.fromkeys(reasons)),
    }


def build_unit_id(row: pd.Series, unit_type: str) -> str:
    if unit_type == "presentation":
        return str(row["presentation_id"])
    return (
        f"{row['participant_id']}_{row['session_id']}"
        f"_t{int(row['transition_position'])}"
    )


def audit_manifest_rows(
    manifest: pd.DataFrame,
    unit_type: str,
    participant: str,
    session: str,
    relative_ts: np.ndarray,
    values: np.ndarray,
    indices: list[int],
    rate: float | None,
    tolerance: float,
    min_ratio: float,
    min_finite: float,
) -> list[dict[str, Any]]:
    subset = manifest[
        (manifest["participant_id"].astype(str) == participant)
        & (manifest["session_id"].astype(str) == session)
    ].copy()

    if unit_type == "presentation":
        start_col, end_col = "timeline_start_sec", "timeline_end_sec"
    else:
        start_col, end_col = "transition_start_sec", "transition_end_sec"

    rows: list[dict[str, Any]] = []
    for _, row in subset.iterrows():
        result = row.to_dict()
        result["raw_emg_unit_id"] = build_unit_id(row, unit_type)
        result["raw_emg_unit_type"] = unit_type
        result["participant_session_key"] = f"{participant}_{session}"
        result.update(
            interval_metrics(
                relative_ts=relative_ts,
                emg_values=values,
                true_indices=indices,
                start_sec=float(row[start_col]),
                end_sec=float(row[end_col]),
                nominal_rate=rate,
                tolerance_sec=tolerance,
                min_sample_ratio=min_ratio,
                min_finite_fraction=min_finite,
            )
        )
        rows.append(result)
    return rows


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
    manifests_dir = repo_root / "manifests"
    docs.mkdir(parents=True, exist_ok=True)

    presentation_path = manifests_dir / "dejavu_stimulus_presentation_manifest.csv"
    transition_path = manifests_dir / "dejavu_transition_manifest.csv"
    if not presentation_path.exists() or not transition_path.exists():
        raise AuditError("Required source manifests are missing")

    presentations = pd.read_csv(presentation_path)
    transitions = pd.read_csv(transition_path)
    xdf_files = sorted(raw_root.glob("sub-*/ses-*/eeg/*.xdf"))
    print(f"Discovered {len(xdf_files)} XDF files")

    session_rows: list[dict[str, Any]] = []
    exception_channel_rows: list[dict[str, Any]] = []
    presentation_rows: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    hard_errors: list[str] = []

    for number, xdf_path in enumerate(xdf_files, start=1):
        participant, session = parse_path_identity(xdf_path)
        key = f"{participant}_{session}"
        print(f"[{number:02d}/{len(xdf_files):02d}] {key}", flush=True)
        try:
            streams, _ = pyxdf.load_xdf(str(xdf_path), verbose=False)
            eeg = find_eeg_stream(streams)
            emg, indices, meta = find_emg_stream(streams)
            values = as_numeric_2d(emg.get("time_series", []))
            emg_ts = np.asarray(emg.get("time_stamps", []), dtype=np.float64).reshape(-1)
            eeg_tm = timestamp_metrics(eeg.get("time_stamps", []))
            emg_tm = timestamp_metrics(emg_ts)
            if eeg_tm["start"] is None:
                raise AuditError("EEG has no finite timestamp origin")
            if values.shape[0] != emg_ts.size:
                raise AuditError(
                    f"EMG sample/timestamp mismatch: {values.shape[0]} vs {emg_ts.size}"
                )
            if values.shape[1] != len(meta):
                raise AuditError(
                    f"EMG descriptor/array mismatch: {values.shape[1]} vs {len(meta)}"
                )
            if len(indices) != 2:
                raise AuditError(f"Expected exactly two true EMG channels, got {indices}")

            relative_ts = emg_ts - float(eeg_tm["start"])
            nominal = float_or_none(emg.get("info", {}).get("nominal_srate"))
            rate = nominal or emg_tm["effective_rate"]

            global_stats = [
                signal_metrics(values[:, channel_index]) for channel_index in indices
            ]
            filename_id = filename_identity(xdf_path)
            identity_conflict = bool(
                filename_id and filename_id != (participant, session)
            )
            duration_ratio = (
                emg_tm["duration"] / eeg_tm["duration"]
                if emg_tm["duration"] is not None
                and eeg_tm["duration"] not in (None, 0)
                else None
            )
            status_reasons: list[str] = []
            for idx, stats in enumerate(global_stats, start=1):
                if stats["finite_fraction"] < args.minimum_finite_fraction:
                    status_reasons.append(f"CH{idx}_NONFINITE")
                if stats["exact_flatline"]:
                    status_reasons.append(f"CH{idx}_FLATLINE")
            if duration_ratio is not None and duration_ratio < 0.95:
                status_reasons.append("SHORT_EMG_COVERAGE")

            session_status = "PASS" if not status_reasons else ";".join(status_reasons)
            session_rows.append(
                {
                    "participant_id": participant,
                    "session_id": session,
                    "participant_session_key": key,
                    "xdf_filename": xdf_path.name,
                    "identity_filename_conflict": identity_conflict,
                    "emg_stream_name": stream_name(emg),
                    "true_emg_channel_indices": ";".join(map(str, indices)),
                    "true_emg_channel_labels": ";".join(
                        meta[i]["label"] for i in indices
                    ),
                    "true_emg_channel_units": ";".join(
                        meta[i]["unit"] for i in indices
                    ),
                    "emg_nominal_rate_hz": nominal,
                    "emg_effective_rate_hz": emg_tm["effective_rate"],
                    "eeg_duration_sec": eeg_tm["duration"],
                    "emg_duration_sec": emg_tm["duration"],
                    "emg_to_eeg_duration_ratio": duration_ratio,
                    "emg_end_relative_to_eeg_sec": (
                        emg_tm["end"] - eeg_tm["start"]
                        if emg_tm["end"] is not None
                        else None
                    ),
                    "session_status": session_status,
                }
            )

            if session_status != "PASS":
                for logical_channel, (channel_index, stats) in enumerate(
                    zip(indices, global_stats), start=1
                ):
                    row = {
                        "participant_id": participant,
                        "session_id": session,
                        "participant_session_key": key,
                        "xdf_filename": xdf_path.name,
                        "logical_emg_channel": logical_channel,
                        "channel_index": channel_index,
                        "channel_label": meta[channel_index]["label"],
                        "channel_unit": meta[channel_index]["unit"],
                    }
                    row.update(stats)
                    exception_channel_rows.append(row)

            presentation_rows.extend(
                audit_manifest_rows(
                    presentations,
                    "presentation",
                    participant,
                    session,
                    relative_ts,
                    values,
                    indices,
                    rate,
                    args.coverage_tolerance_sec,
                    args.minimum_sample_ratio,
                    args.minimum_finite_fraction,
                )
            )
            transition_rows.extend(
                audit_manifest_rows(
                    transitions,
                    "transition",
                    participant,
                    session,
                    relative_ts,
                    values,
                    indices,
                    rate,
                    args.coverage_tolerance_sec,
                    args.minimum_sample_ratio,
                    args.minimum_finite_fraction,
                )
            )
        except Exception as exc:
            traceback.print_exc()
            hard_errors.append(key)
            session_rows.append(
                {
                    "participant_id": participant,
                    "session_id": session,
                    "participant_session_key": key,
                    "xdf_filename": xdf_path.name,
                    "identity_filename_conflict": False,
                    "emg_stream_name": "",
                    "true_emg_channel_indices": "",
                    "true_emg_channel_labels": "",
                    "true_emg_channel_units": "",
                    "emg_nominal_rate_hz": None,
                    "emg_effective_rate_hz": None,
                    "eeg_duration_sec": None,
                    "emg_duration_sec": None,
                    "emg_to_eeg_duration_ratio": None,
                    "emg_end_relative_to_eeg_sec": None,
                    "session_status": f"ERROR:{type(exc).__name__}:{exc}",
                }
            )
        finally:
            try:
                del streams
            except UnboundLocalError:
                pass
            gc.collect()

    session_df = pd.DataFrame(session_rows).sort_values(
        ["participant_id", "session_id"]
    )
    exception_df = pd.DataFrame(exception_channel_rows)
    presentation_df = pd.DataFrame(presentation_rows).sort_values(
        ["participant_id", "session_id", "chronological_position"]
    )
    transition_df = pd.DataFrame(transition_rows).sort_values(
        ["participant_id", "session_id", "transition_position"]
    )

    session_csv = docs / "dejavu_raw_emg_eligibility_by_session.csv"
    exception_csv = docs / "dejavu_raw_emg_exception_channel_forensics.csv"
    presentation_csv = (
        manifests_dir / "dejavu_stimulus_presentation_emg_eligibility.csv"
    )
    transition_csv = manifests_dir / "dejavu_transition_emg_eligibility.csv"
    session_df.to_csv(session_csv, index=False)
    exception_df.to_csv(exception_csv, index=False)
    presentation_df.to_csv(presentation_csv, index=False)
    transition_df.to_csv(transition_csv, index=False)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "xdf_files": int(len(xdf_files)),
        "hard_errors": hard_errors,
        "session_status_counts": session_df["session_status"]
        .value_counts()
        .to_dict(),
        "presentation_rows": int(len(presentation_df)),
        "presentation_two_channel_eligible": int(
            presentation_df["raw_emg_two_channel_eligible"].sum()
        ),
        "presentation_one_channel_eligible": int(
            presentation_df["raw_emg_one_channel_eligible"].sum()
        ),
        "transition_rows": int(len(transition_df)),
        "transition_two_channel_eligible": int(
            transition_df["raw_emg_two_channel_eligible"].sum()
        ),
        "transition_one_channel_eligible": int(
            transition_df["raw_emg_one_channel_eligible"].sum()
        ),
        "ineligible_presentation_sessions": sorted(
            presentation_df.loc[
                ~presentation_df["raw_emg_two_channel_eligible"],
                "participant_session_key",
            ].unique().tolist()
        ),
        "ineligible_transition_sessions": sorted(
            transition_df.loc[
                ~transition_df["raw_emg_two_channel_eligible"],
                "participant_session_key",
            ].unique().tolist()
        ),
        "presentation_reason_counts": presentation_df[
            "raw_emg_eligibility_reason"
        ]
        .value_counts()
        .to_dict(),
        "transition_reason_counts": transition_df["raw_emg_eligibility_reason"]
        .value_counts()
        .to_dict(),
        "criteria": {
            "minimum_sample_ratio": args.minimum_sample_ratio,
            "minimum_finite_fraction": args.minimum_finite_fraction,
            "coverage_tolerance_sec": args.coverage_tolerance_sec,
            "flatline_rule": "exact flatline only: one unique finite value, zero std, or zero p01-p99 range",
        },
    }
    json_path = docs / "dejavu_emg_pairing_capacity.json"
    json_path.write_text(
        json.dumps(json_safe(summary), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    report_path = docs / "dejavu_emg_pairing_capacity.md"
    problematic = session_df[session_df["session_status"] != "PASS"]
    lines = [
        "# DEJA-VU Raw EMG Pairing-Capacity Audit",
        "",
        f"Generated: `{summary['generated_at_utc']}`",
        "",
        "This is a read-only event-level audit using the true EMG channels resolved from raw XDF descriptors. "
        "No filtering, resampling, segmentation output, or training was performed.",
        "",
        "## Capacity",
        "",
        "| Unit | Total | Strict two-channel EMG eligible | At least one EMG channel eligible |",
        "|---|---:|---:|---:|",
        f"| Stimulus presentations | {summary['presentation_rows']} | {summary['presentation_two_channel_eligible']} | {summary['presentation_one_channel_eligible']} |",
        f"| Transition intervals | {summary['transition_rows']} | {summary['transition_two_channel_eligible']} | {summary['transition_one_channel_eligible']} |",
        "",
        "Strict eligibility requires full timestamp/sample coverage, at least 99.9% finite samples in each true EMG channel, "
        "and no exact flatline in either channel.",
        "",
        "## Problematic sessions",
        "",
        "| Participant-session | Status | EMG/EEG duration ratio | EMG end relative to EEG (s) |",
        "|---|---|---:|---:|",
    ]
    for _, row in problematic.iterrows():
        lines.append(
            f"| {row['participant_session_key']} | {row['session_status']} | "
            f"{row['emg_to_eeg_duration_ratio']} | {row['emg_end_relative_to_eeg_sec']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Use `raw_emg_two_channel_eligible=True` for the strict paired EEG+EMG dataset.",
            "- `raw_emg_one_channel_eligible=True` is reported only as a diagnostic salvage option; it is not automatically authorized as a modeling policy.",
            "- The official distributed EMG HDF5 groups remain invalid because they contain hard-coded columns 0–1 rather than the descriptor-confirmed true EMG channels.",
            "- The enriched manifests do not replace the original presentation and transition manifests.",
            "",
            "## Outputs",
            "",
            "- `docs/dejavu_raw_emg_eligibility_by_session.csv`",
            "- `docs/dejavu_raw_emg_exception_channel_forensics.csv`",
            "- `manifests/dejavu_stimulus_presentation_emg_eligibility.csv`",
            "- `manifests/dejavu_transition_emg_eligibility.csv`",
            "- `docs/dejavu_emg_pairing_capacity.json`",
            "",
        ]
    )
    report_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nDEJA-VU EMG ELIGIBILITY CHECKPOINT")
    print(
        "Presentations strict two-channel eligible: "
        f"{summary['presentation_two_channel_eligible']}/{summary['presentation_rows']}"
    )
    print(
        "Presentations one-channel eligible: "
        f"{summary['presentation_one_channel_eligible']}/{summary['presentation_rows']}"
    )
    print(
        "Transitions strict two-channel eligible: "
        f"{summary['transition_two_channel_eligible']}/{summary['transition_rows']}"
    )
    print(
        "Transitions one-channel eligible: "
        f"{summary['transition_one_channel_eligible']}/{summary['transition_rows']}"
    )
    print(f"Report: {report_path}")
    return 1 if hard_errors else 0


if __name__ == "__main__":
    sys.exit(main())

