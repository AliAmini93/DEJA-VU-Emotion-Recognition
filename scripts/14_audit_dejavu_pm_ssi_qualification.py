#!/usr/bin/env python3
"""Final data-only qualification audit for DEJA-VU in PM-SSI-DG Paper 1.

This script does not train a model and does not extract learned features.
It audits whether the frozen Cohort B and repeated 3x3 Joint
Subject–Exact-Video protocol can support:

- paired EEG+EMG physical trials constructed from Raw XDF;
- 5 s non-overlapping paired windows;
- strict PM-SSI donors:
    same class,
    different participant,
    different exact video,
    different physical trial,
    source-training only,
    paired EEG+EMG from one real donor presentation;
- leakage-safe inner joint source validation;
- a final GREEN / YELLOW / RED dataset-role decision.

The script is read-only with respect to the dataset.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import pyxdf


DEFAULT_REPO = Path("/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition")
DEFAULT_DATA = Path("/mnt/HDD/AliWorks/DEJA-VU")

TASKS = ("valence", "arousal")
POLICIES = (
    "discard_midpoint",
    "midpoint_as_low",
    "midpoint_as_high",
)
EXPECTED_REPETITIONS = (0, 1, 2, 3, 4)
EXPECTED_FOLDS = (1, 2, 3)
WINDOW_SEC = 5.0

# Raw DSI_FLEX descriptors are generic device labels. The official
# DEJA-VU preprocessing map, independently audited across all 34 XDF files, is:
# F3->FP1, S2->FP2, S3->C3, S4->C4, S5->LE, S6->EOG1, S7->EOG2.
# There is no Fz channel in the distributed Raw XDF descriptor or official map.
EEG_DESCRIPTOR_MAP = {
    "F3": "FP1",
    "S2": "FP2",
    "S3": "C3",
    "S4": "C4",
    "S5": "LE",
    "S6": "EOG1",
    "S7": "EOG2",
}
MODEL_EEG_RAW_LABELS = ("F3", "S2", "S3", "S4")
AUX_EEG_RAW_LABELS = ("S5", "S6", "S7")
EMG_RE = re.compile(r"(^|_)EMG_CH([12])(_|$)", re.I)
SUB_RE = re.compile(r"^sub-(P\d+)$", re.I)
SES_RE = re.compile(r"^ses-(S\d+)$", re.I)

OUTPUT_NAMES = {
    "raw_windows": "dejavu_pm_ssi_raw_window_constructibility.csv",
    "anchor_support": "dejavu_pm_ssi_donor_anchor_support.csv.gz",
    "cell_support": "dejavu_pm_ssi_donor_cell_support.csv",
    "protocol_summary": "dejavu_pm_ssi_donor_protocol_summary.csv",
    "inner_support": "dejavu_pm_ssi_inner_joint_support.csv",
    "test_support": "dejavu_pm_ssi_outer_test_support.csv",
    "report_md": "dejavu_pm_ssi_final_qualification.md",
    "report_json": "dejavu_pm_ssi_final_qualification.json",
}


class AuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class RawSessionResult:
    participant_session_key: str
    participant_id: str
    session_id: str
    xdf_path: str
    xdf_found: bool
    raw_loaded: bool
    eeg_stream_name: str
    emg_stream_name: str
    eeg_labels: str
    emg_labels: str
    required_eeg_labels_present: bool
    true_emg_channels_resolved: bool
    eeg_rate_hz: float | None
    emg_rate_hz: float | None
    error: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--window-sec", type=float, default=WINDOW_SEC)
    parser.add_argument(
        "--skip-raw-xdf",
        action="store_true",
        help=(
            "Use the frozen manifest coverage fields without reopening XDF. "
            "Not recommended for the final qualification."
        ),
    )
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def git_value(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unavailable"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scalar(value: Any, default: str = "") -> str:
    while isinstance(value, (list, tuple)):
        if not value:
            return default
        value = value[0]
    return default if value is None else str(value)


def finite_float(value: Any) -> float | None:
    try:
        number = float(scalar(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def stream_name(stream: dict[str, Any]) -> str:
    return scalar(stream.get("info", {}).get("name"))


def stream_type(stream: dict[str, Any]) -> str:
    return scalar(stream.get("info", {}).get("type"))


def channel_meta(stream: dict[str, Any]) -> list[dict[str, str]]:
    try:
        desc = stream["info"]["desc"][0]
        items = desc["channels"][0]["channel"]
        if isinstance(items, dict):
            items = [items]
    except (KeyError, IndexError, TypeError):
        items = []
    output: list[dict[str, str]] = []
    for index, item in enumerate(items):
        item = item if isinstance(item, dict) else {}
        output.append(
            {
                "index": str(index),
                "label": scalar(item.get("label"), f"channel_{index}"),
                "unit": scalar(item.get("unit")),
                "type": scalar(item.get("type")),
            }
        )
    return output


def find_eeg(streams: list[dict[str, Any]]) -> dict[str, Any]:
    exact = [
        stream
        for stream in streams
        if stream_name(stream).upper() == "DSI_FLEX"
    ]
    if len(exact) == 1:
        return exact[0]
    typed = [
        stream
        for stream in streams
        if stream_type(stream).upper() == "EEG"
    ]
    if len(typed) == 1:
        return typed[0]
    raise AuditError(
        f"EEG stream unresolved: exact={len(exact)}, typed={len(typed)}"
    )


def true_emg_indices(labels: list[str]) -> list[int]:
    found: list[tuple[int, int]] = []
    for index, label in enumerate(labels):
        upper = label.upper()
        if "STATUS" in upper or "BATTERY" in upper:
            continue
        match = EMG_RE.search(upper)
        if match:
            found.append((int(match.group(2)), index))
    found.sort()
    return [index for _, index in found]


def find_emg(
    streams: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[int], list[dict[str, str]]]:
    candidates = []
    for stream in streams:
        metadata = channel_meta(stream)
        indices = true_emg_indices([row["label"] for row in metadata])
        if len(indices) >= 2:
            candidates.append((stream, indices[:2], metadata))
    exact = [
        candidate
        for candidate in candidates
        if stream_name(candidate[0]).upper() == "SHIMMER_BBBD"
    ]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    raise AuditError(
        "Descriptor-confirmed EMG stream unresolved: "
        f"{[stream_name(candidate[0]) for candidate in candidates]}"
    )


def as_numeric_2d(values: Any) -> np.ndarray:
    array = np.asarray(values)
    if array.ndim == 1:
        array = array[:, None]
    if array.ndim != 2:
        raise AuditError(f"Expected 2-D signal array, got {array.shape}")
    return array.astype(np.float64, copy=False)


def effective_rate(timestamps: np.ndarray) -> float | None:
    finite = timestamps[np.isfinite(timestamps)]
    if finite.size < 2:
        return None
    differences = np.diff(finite)
    positive = differences[differences > 0]
    if not positive.size:
        return None
    median_gap = float(np.median(positive))
    return 1.0 / median_gap if median_gap > 0 else None


def normalized_label(label: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", label.upper())


def identity_from_path(path: Path) -> tuple[str, str]:
    participant = ""
    session = ""
    for part in path.parts:
        sub_match = SUB_RE.match(part)
        ses_match = SES_RE.match(part)
        if sub_match:
            participant = sub_match.group(1).upper()
        if ses_match:
            session = ses_match.group(1).upper()
    if not participant or not session:
        raise AuditError(f"Cannot parse participant/session from {path}")
    return participant, session


def build_xdf_index(raw_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in sorted(raw_root.glob("sub-*/ses-*/eeg/*.xdf")):
        participant, session = identity_from_path(path)
        key = f"{participant}_{session}"
        if key in index:
            raise AuditError(f"Duplicate XDF path for {key}")
        index[key] = path
    return index


def interval_samples(
    timestamps: np.ndarray,
    values: np.ndarray,
    channel_indices: list[int],
    start: float,
    end: float,
    expected_rate: float,
) -> tuple[int, float, bool, bool]:
    selected_indices = np.flatnonzero(
        np.isfinite(timestamps)
        & (timestamps >= start)
        & (timestamps < end)
    )
    observed = int(selected_indices.size)
    expected = max(int(round((end - start) * expected_rate)), 1)
    coverage = min(observed / expected, 1.0)
    if observed < 2:
        return observed, coverage, False, False

    selected_timestamps = timestamps[selected_indices]
    differences = np.diff(selected_timestamps)
    positive = differences[differences > 0]
    max_gap = float(np.max(positive)) if positive.size else math.inf
    gap_ok = bool(
        positive.size
        and max_gap <= max(5.0 / expected_rate, 0.05)
    )

    selected_values = values[np.ix_(selected_indices, channel_indices)]
    finite_ok = bool(np.isfinite(selected_values).all())
    variable_ok = bool(
        selected_values.shape[0] >= 2
        and np.all(np.nanstd(selected_values, axis=0) > 0)
    )
    return observed, coverage, gap_ok and finite_ok, variable_ok


def audit_raw_windows(
    manifest: pd.DataFrame,
    raw_root: Path,
    window_sec: float,
    skip_raw_xdf: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    xdf_index = build_xdf_index(raw_root)
    retained_sessions = sorted(
        manifest["participant_session_key"].astype(str).unique()
    )
    rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []

    if skip_raw_xdf:
        for record in manifest.itertuples(index=False):
            duration = float(record.timeline_duration_sec)
            candidate = int(math.floor(duration / window_sec))
            manifest_pass = bool(
                record.eeg_available
                and record.strict_two_channel_emg_eligible
                and record.raw_emg_boundary_covered
                and record.raw_emg_gap_ok
                and float(record.raw_emg_sample_coverage_ratio) >= 0.98
            )
            rows.append(
                {
                    "presentation_id": record.presentation_id,
                    "participant_id": record.participant_id,
                    "session_id": record.session_id,
                    "participant_session_key": (
                        record.participant_session_key
                    ),
                    "video_name": record.video_name,
                    "canonical_quadrant": record.canonical_quadrant,
                    "duration_sec": duration,
                    "candidate_5s_windows": candidate,
                    "paired_valid_5s_windows": (
                        candidate if manifest_pass else 0
                    ),
                    "paired_window_fraction": (
                        1.0 if candidate and manifest_pass else 0.0
                    ),
                    "minimum_two_windows": bool(
                        candidate >= 2 and manifest_pass
                    ),
                    "raw_scan_mode": "FROZEN_MANIFEST_ONLY",
                    "raw_error": "",
                }
            )
        return pd.DataFrame(rows), pd.DataFrame(session_rows)

    missing = [
        session for session in retained_sessions if session not in xdf_index
    ]
    if missing:
        raise AuditError(f"Retained XDF files missing: {missing}")

    grouped = {
        key: frame.copy()
        for key, frame in manifest.groupby("participant_session_key")
    }

    for number, key in enumerate(retained_sessions, 1):
        path = xdf_index[key]
        participant_id, session_id = key.split("_", 1)
        print(
            f"[Raw XDF {number:02d}/{len(retained_sessions):02d}] "
            f"{key}: {path.name}",
            flush=True,
        )
        streams: list[dict[str, Any]] | None = None
        try:
            streams, _ = pyxdf.load_xdf(str(path), verbose=False)
            eeg = find_eeg(streams)
            emg, emg_indices, emg_metadata = find_emg(streams)

            eeg_metadata = channel_meta(eeg)
            eeg_labels = [item["label"] for item in eeg_metadata]
            eeg_label_map = {
                normalized_label(label): index
                for index, label in enumerate(eeg_labels)
            }
            expected_raw_labels = (
                MODEL_EEG_RAW_LABELS + AUX_EEG_RAW_LABELS
            )
            missing_raw_labels = [
                label
                for label in expected_raw_labels
                if normalized_label(label) not in eeg_label_map
            ]
            if missing_raw_labels:
                raise AuditError(
                    f"{key}: required raw DSI descriptors missing: "
                    f"{missing_raw_labels}; available={eeg_labels}"
                )
            required_indices = [
                eeg_label_map[normalized_label(label)]
                for label in MODEL_EEG_RAW_LABELS
            ]

            eeg_values = as_numeric_2d(eeg.get("time_series", []))
            emg_values = as_numeric_2d(emg.get("time_series", []))
            eeg_timestamps_absolute = np.asarray(
                eeg.get("time_stamps", []),
                dtype=float,
            ).reshape(-1)
            emg_timestamps_absolute = np.asarray(
                emg.get("time_stamps", []),
                dtype=float,
            ).reshape(-1)
            if eeg_timestamps_absolute.size < 2:
                raise AuditError(f"{key}: insufficient EEG timestamps")
            origin = float(eeg_timestamps_absolute[np.isfinite(
                eeg_timestamps_absolute
            )][0])
            eeg_timestamps = eeg_timestamps_absolute - origin
            emg_timestamps = emg_timestamps_absolute - origin

            eeg_nominal = finite_float(
                eeg.get("info", {}).get("nominal_srate")
            )
            emg_nominal = finite_float(
                emg.get("info", {}).get("nominal_srate")
            )
            eeg_rate = eeg_nominal or effective_rate(eeg_timestamps)
            emg_rate = emg_nominal or effective_rate(emg_timestamps)
            if not eeg_rate or not emg_rate:
                raise AuditError(f"{key}: sample rate unresolved")

            if eeg_values.shape[0] != eeg_timestamps.shape[0]:
                raise AuditError(
                    f"{key}: EEG values/timestamp mismatch "
                    f"{eeg_values.shape[0]} != {eeg_timestamps.shape[0]}"
                )
            if emg_values.shape[0] != emg_timestamps.shape[0]:
                raise AuditError(
                    f"{key}: EMG values/timestamp mismatch "
                    f"{emg_values.shape[0]} != {emg_timestamps.shape[0]}"
                )

            session_rows.append(
                asdict(
                    RawSessionResult(
                        participant_session_key=key,
                        participant_id=participant_id,
                        session_id=session_id,
                        xdf_path=str(path),
                        xdf_found=True,
                        raw_loaded=True,
                        eeg_stream_name=stream_name(eeg),
                        emg_stream_name=stream_name(emg),
                        eeg_labels=";".join(
                            f"{label}->{EEG_DESCRIPTOR_MAP.get(label, label)}"
                            for label in eeg_labels
                            if label != "TRG"
                        ),
                        emg_labels=";".join(
                            emg_metadata[index]["label"]
                            for index in emg_indices
                        ),
                        required_eeg_labels_present=True,
                        true_emg_channels_resolved=(
                            len(emg_indices) == 2
                        ),
                        eeg_rate_hz=float(eeg_rate),
                        emg_rate_hz=float(emg_rate),
                        error="",
                    )
                )
            )

            for record in grouped[key].itertuples(index=False):
                start = float(record.timeline_start_sec)
                end = float(record.timeline_end_sec)
                duration = end - start
                candidate_count = int(
                    math.floor(duration / window_sec)
                )
                paired_count = 0
                eeg_coverage_values: list[float] = []
                emg_coverage_values: list[float] = []
                invalid_reasons: list[str] = []

                for index in range(candidate_count):
                    window_start = start + index * window_sec
                    window_end = window_start + window_sec

                    _, eeg_coverage, eeg_integrity, eeg_variable = (
                        interval_samples(
                            eeg_timestamps,
                            eeg_values,
                            required_indices,
                            window_start,
                            window_end,
                            float(eeg_rate),
                        )
                    )
                    _, emg_coverage, emg_integrity, emg_variable = (
                        interval_samples(
                            emg_timestamps,
                            emg_values,
                            emg_indices,
                            window_start,
                            window_end,
                            float(emg_rate),
                        )
                    )
                    eeg_coverage_values.append(eeg_coverage)
                    emg_coverage_values.append(emg_coverage)

                    valid = bool(
                        eeg_coverage >= 0.98
                        and emg_coverage >= 0.98
                        and eeg_integrity
                        and emg_integrity
                        and eeg_variable
                        and emg_variable
                    )
                    if valid:
                        paired_count += 1
                    else:
                        invalid_reasons.append(
                            f"w{index}:"
                            f"eeg_cov={eeg_coverage:.3f},"
                            f"emg_cov={emg_coverage:.3f},"
                            f"eeg_integrity={eeg_integrity},"
                            f"emg_integrity={emg_integrity},"
                            f"eeg_variable={eeg_variable},"
                            f"emg_variable={emg_variable}"
                        )

                rows.append(
                    {
                        "presentation_id": record.presentation_id,
                        "participant_id": record.participant_id,
                        "session_id": record.session_id,
                        "participant_session_key": key,
                        "video_name": record.video_name,
                        "canonical_quadrant": (
                            record.canonical_quadrant
                        ),
                        "duration_sec": duration,
                        "candidate_5s_windows": candidate_count,
                        "paired_valid_5s_windows": paired_count,
                        "paired_window_fraction": (
                            paired_count / candidate_count
                            if candidate_count
                            else 0.0
                        ),
                        "minimum_two_windows": bool(
                            paired_count >= 2
                        ),
                        "minimum_eeg_window_coverage": (
                            min(eeg_coverage_values)
                            if eeg_coverage_values
                            else 0.0
                        ),
                        "minimum_emg_window_coverage": (
                            min(emg_coverage_values)
                            if emg_coverage_values
                            else 0.0
                        ),
                        "raw_scan_mode": "RAW_XDF",
                        "raw_error": " | ".join(
                            invalid_reasons[:5]
                        ),
                    }
                )
        except Exception as exc:
            traceback.print_exc()
            session_rows.append(
                asdict(
                    RawSessionResult(
                        participant_session_key=key,
                        participant_id=participant_id,
                        session_id=session_id,
                        xdf_path=str(path),
                        xdf_found=path.exists(),
                        raw_loaded=False,
                        eeg_stream_name="",
                        emg_stream_name="",
                        eeg_labels="",
                        emg_labels="",
                        required_eeg_labels_present=False,
                        true_emg_channels_resolved=False,
                        eeg_rate_hz=None,
                        emg_rate_hz=None,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
            )
            for record in grouped[key].itertuples(index=False):
                rows.append(
                    {
                        "presentation_id": record.presentation_id,
                        "participant_id": record.participant_id,
                        "session_id": record.session_id,
                        "participant_session_key": key,
                        "video_name": record.video_name,
                        "canonical_quadrant": (
                            record.canonical_quadrant
                        ),
                        "duration_sec": float(
                            record.timeline_duration_sec
                        ),
                        "candidate_5s_windows": int(
                            math.floor(
                                float(record.timeline_duration_sec)
                                / window_sec
                            )
                        ),
                        "paired_valid_5s_windows": 0,
                        "paired_window_fraction": 0.0,
                        "minimum_two_windows": False,
                        "minimum_eeg_window_coverage": 0.0,
                        "minimum_emg_window_coverage": 0.0,
                        "raw_scan_mode": "RAW_XDF_ERROR",
                        "raw_error": f"{type(exc).__name__}: {exc}",
                    }
                )
        finally:
            if streams is not None:
                del streams
            gc.collect()

    return pd.DataFrame(rows), pd.DataFrame(session_rows)


def boolean_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False)
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "yes", "y"})
    )


def prepare_manifest(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "participant_id",
        "session_id",
        "participant_session_key",
        "presentation_id",
        "video_name",
        "canonical_quadrant",
        "chronological_position",
        "timeline_start_sec",
        "timeline_end_sec",
        "timeline_duration_sec",
        "eeg_available",
        "strict_two_channel_emg_eligible",
        "raw_emg_boundary_covered",
        "raw_emg_gap_ok",
        "raw_emg_sample_coverage_ratio",
        "after_valence",
        "after_arousal",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise AuditError(f"Manifest columns missing: {missing}")

    output = frame.copy()
    for column in (
        "participant_id",
        "session_id",
        "participant_session_key",
        "presentation_id",
        "video_name",
        "canonical_quadrant",
    ):
        output[column] = output[column].astype(str)
    for column in (
        "eeg_available",
        "strict_two_channel_emg_eligible",
        "raw_emg_boundary_covered",
        "raw_emg_gap_ok",
    ):
        output[column] = boolean_series(output[column])

    if len(output) != 90:
        raise AuditError(f"Expected 90 emotional presentations, found {len(output)}")
    if output["participant_id"].nunique() != 24:
        raise AuditError("Expected 24 independent participants")
    if output["participant_session_key"].nunique() != 30:
        raise AuditError("Expected 30 participant-sessions")
    if output["video_name"].nunique() != 16:
        raise AuditError("Expected 16 exact videos")
    if output["presentation_id"].duplicated().any():
        raise AuditError("Duplicate presentation_id values")

    for task in TASKS:
        score = pd.to_numeric(output[f"after_{task}"], errors="coerce")
        if score.isna().any() or not score.between(1, 9).all():
            raise AuditError(f"Invalid after_{task} scores")
        output[f"{task}_discard_midpoint"] = pd.Series(
            np.where(score < 5, 0, np.where(score > 5, 1, np.nan)),
            index=output.index,
            dtype="Float64",
        )
        output[f"{task}_midpoint_as_low"] = (
            (score > 5).astype(int)
        )
        output[f"{task}_midpoint_as_high"] = (
            (score >= 5).astype(int)
        )

    expected_primary = {
        "valence": (75, 53, 22),
        "arousal": (71, 33, 38),
    }
    for task, expected in expected_primary.items():
        labels = output[f"{task}_discard_midpoint"]
        observed = (
            int(labels.notna().sum()),
            int((labels == 0).sum()),
            int((labels == 1).sum()),
        )
        if observed != expected:
            raise AuditError(
                f"Unexpected {task} primary support: {observed}; "
                f"expected={expected}"
            )

    paired = (
        output["eeg_available"]
        & output["strict_two_channel_emg_eligible"]
        & output["raw_emg_boundary_covered"]
        & output["raw_emg_gap_ok"]
        & (
            pd.to_numeric(
                output["raw_emg_sample_coverage_ratio"],
                errors="coerce",
            )
            >= 0.98
        )
    )
    if not paired.all():
        failed = output.loc[~paired, "presentation_id"].tolist()
        raise AuditError(
            "Cohort B manifest contains non-paired rows: "
            f"{failed}"
        )
    output["frozen_paired_eligible"] = paired
    return output


def validate_assignments(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"entity_type", "entity_id", "repetition", "fold"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise AuditError(f"Assignment columns missing: {missing}")
    output = frame.copy()
    output["entity_type"] = output["entity_type"].astype(str)
    output["entity_id"] = output["entity_id"].astype(str)
    output["repetition"] = pd.to_numeric(
        output["repetition"],
        errors="raise",
    ).astype(int)
    output["fold"] = pd.to_numeric(
        output["fold"],
        errors="raise",
    ).astype(int)

    if tuple(sorted(output["repetition"].unique())) != EXPECTED_REPETITIONS:
        raise AuditError("Expected repetitions 0-4")
    for repetition in EXPECTED_REPETITIONS:
        subset = output[output["repetition"] == repetition]
        participants = subset[subset["entity_type"] == "participant"]
        videos = subset[subset["entity_type"] == "video"]
        if participants["entity_id"].nunique() != 24:
            raise AuditError(f"rep{repetition}: participant count mismatch")
        if videos["entity_id"].nunique() != 16:
            raise AuditError(f"rep{repetition}: video count mismatch")
        if tuple(sorted(participants["fold"].unique())) != EXPECTED_FOLDS:
            raise AuditError(f"rep{repetition}: participant folds mismatch")
        if tuple(sorted(videos["fold"].unique())) != EXPECTED_FOLDS:
            raise AuditError(f"rep{repetition}: video folds mismatch")
    return output


def assignment_maps(
    assignments: pd.DataFrame,
    repetition: int,
) -> tuple[dict[str, int], dict[str, int]]:
    subset = assignments[assignments["repetition"] == repetition]
    participant_map = {
        str(row.entity_id): int(row.fold)
        for row in subset[
            subset["entity_type"] == "participant"
        ].itertuples()
    }
    video_map = {
        str(row.entity_id): int(row.fold)
        for row in subset[
            subset["entity_type"] == "video"
        ].itertuples()
    }
    return participant_map, video_map


def quantile(values: pd.Series, probability: float) -> float:
    if values.empty:
        return float("nan")
    return float(
        np.quantile(
            pd.to_numeric(values, errors="coerce").dropna(),
            probability,
        )
    )


def summarize_donors(anchor_frame: pd.DataFrame) -> dict[str, Any]:
    if anchor_frame.empty:
        return {
            "anchor_count": 0,
            "donor_min": 0,
            "donor_p10": 0.0,
            "donor_median": 0.0,
            "donor_max": 0,
            "zero_donor_rate": 1.0,
            "below_5_rate": 1.0,
            "below_20_rate": 1.0,
            "unique_subject_min": 0,
            "unique_video_min": 0,
            "unique_quadrant_min": 0,
            "same_quadrant_donor_fraction_median": None,
        }
    donor_count = anchor_frame["eligible_donor_count"].astype(int)
    return {
        "anchor_count": int(len(anchor_frame)),
        "donor_min": int(donor_count.min()),
        "donor_p10": quantile(donor_count, 0.10),
        "donor_median": float(donor_count.median()),
        "donor_max": int(donor_count.max()),
        "zero_donor_rate": float((donor_count == 0).mean()),
        "below_5_rate": float((donor_count < 5).mean()),
        "below_20_rate": float((donor_count < 20).mean()),
        "unique_subject_min": int(
            anchor_frame["unique_donor_subjects"].min()
        ),
        "unique_video_min": int(
            anchor_frame["unique_donor_videos"].min()
        ),
        "unique_quadrant_min": int(
            anchor_frame["unique_donor_quadrants"].min()
        ),
        "same_quadrant_donor_fraction_median": (
            float(
                anchor_frame[
                    "same_quadrant_donor_fraction"
                ].dropna().median()
            )
            if anchor_frame[
                "same_quadrant_donor_fraction"
            ].notna().any()
            else None
        ),
    }


def donor_rows_for_region(
    region: pd.DataFrame,
    task: str,
    policy: str,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    label_column = f"{task}_{policy}"
    labels = pd.to_numeric(region[label_column], errors="coerce")
    usable = region[
        labels.notna()
        & region["raw_window_constructible"].astype(bool)
    ].copy()
    usable["audit_label"] = labels.loc[usable.index].astype(int)

    rows: list[dict[str, Any]] = []
    for anchor in usable.itertuples(index=False):
        legal = usable[
            (usable["audit_label"] == int(anchor.audit_label))
            & (
                usable["participant_id"]
                != str(anchor.participant_id)
            )
            & (usable["video_name"] != str(anchor.video_name))
            & (
                usable["presentation_id"]
                != str(anchor.presentation_id)
            )
        ].copy()

        same_quadrant = (
            legal["canonical_quadrant"].astype(str)
            == str(anchor.canonical_quadrant)
        )
        rows.append(
            {
                **metadata,
                "task": task,
                "label_policy": policy,
                "anchor_presentation_id": anchor.presentation_id,
                "anchor_participant_id": anchor.participant_id,
                "anchor_session_id": anchor.session_id,
                "anchor_video_name": anchor.video_name,
                "anchor_quadrant": anchor.canonical_quadrant,
                "anchor_position": int(anchor.chronological_position),
                "anchor_class": int(anchor.audit_label),
                "source_region_rows": int(len(region)),
                "source_scored_paired_rows": int(len(usable)),
                "eligible_donor_count": int(len(legal)),
                "unique_donor_subjects": int(
                    legal["participant_id"].nunique()
                ),
                "unique_donor_videos": int(
                    legal["video_name"].nunique()
                ),
                "unique_donor_quadrants": int(
                    legal["canonical_quadrant"].nunique()
                ),
                "unique_donor_positions": int(
                    legal["chronological_position"].nunique()
                ),
                "same_quadrant_donor_count": int(
                    same_quadrant.sum()
                ),
                "same_quadrant_donor_fraction": (
                    float(same_quadrant.mean())
                    if len(legal)
                    else None
                ),
                "donor_subject_ids": ";".join(
                    sorted(legal["participant_id"].astype(str).unique())
                ),
                "donor_video_names": ";".join(
                    sorted(legal["video_name"].astype(str).unique())
                ),
                "donor_quadrants": ";".join(
                    sorted(
                        legal["canonical_quadrant"]
                        .astype(str)
                        .unique()
                    )
                ),
            }
        )
    return rows


def build_outer_audit(
    manifest: pd.DataFrame,
    assignments: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    anchor_rows: list[dict[str, Any]] = []
    cell_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    for repetition in EXPECTED_REPETITIONS:
        participant_map, video_map = assignment_maps(
            assignments,
            repetition,
        )
        participant_fold = manifest["participant_id"].map(
            participant_map
        )
        video_fold = manifest["video_name"].map(video_map)
        if participant_fold.isna().any() or video_fold.isna().any():
            raise AuditError(
                f"rep{repetition}: incomplete frozen assignment map"
            )

        for held_subject_fold in EXPECTED_FOLDS:
            for held_video_fold in EXPECTED_FOLDS:
                outer_cell = (
                    f"R{repetition:02d}_S{held_subject_fold}"
                    f"_V{held_video_fold}"
                )
                source = manifest[
                    (participant_fold != held_subject_fold)
                    & (video_fold != held_video_fold)
                ].copy()
                test = manifest[
                    (participant_fold == held_subject_fold)
                    & (video_fold == held_video_fold)
                ].copy()

                base = {
                    "repetition": repetition,
                    "role": (
                        "primary"
                        if repetition == 0
                        else "sensitivity"
                    ),
                    "held_subject_fold": held_subject_fold,
                    "held_video_fold": held_video_fold,
                    "outer_cell": outer_cell,
                    "source_subjects": int(
                        source["participant_id"].nunique()
                    ),
                    "source_videos": int(
                        source["video_name"].nunique()
                    ),
                    "source_rows": int(len(source)),
                    "test_subjects": int(
                        test["participant_id"].nunique()
                    ),
                    "test_videos": int(
                        test["video_name"].nunique()
                    ),
                    "test_rows": int(len(test)),
                }

                for task in TASKS:
                    for policy in POLICIES:
                        generated = donor_rows_for_region(
                            source,
                            task,
                            policy,
                            base,
                        )
                        anchor_rows.extend(generated)
                        summary = summarize_donors(
                            pd.DataFrame(generated)
                        )
                        labels = pd.to_numeric(
                            source[f"{task}_{policy}"],
                            errors="coerce",
                        )
                        scored = source[labels.notna()].copy()
                        scored_labels = labels.loc[
                            scored.index
                        ].astype(int)
                        cell_rows.append(
                            {
                                **base,
                                "task": task,
                                "label_policy": policy,
                                "source_scored_rows": int(
                                    len(scored)
                                ),
                                "source_low": int(
                                    (scored_labels == 0).sum()
                                ),
                                "source_high": int(
                                    (scored_labels == 1).sum()
                                ),
                                "source_both_classes": bool(
                                    scored_labels.nunique() == 2
                                ),
                                **summary,
                            }
                        )

                        test_labels = pd.to_numeric(
                            test[f"{task}_{policy}"],
                            errors="coerce",
                        )
                        test_scored = test[
                            test_labels.notna()
                        ].copy()
                        test_values = test_labels.loc[
                            test_scored.index
                        ].astype(int)
                        test_rows.append(
                            {
                                **base,
                                "task": task,
                                "label_policy": policy,
                                "test_scored_rows": int(
                                    len(test_scored)
                                ),
                                "test_low": int(
                                    (test_values == 0).sum()
                                ),
                                "test_high": int(
                                    (test_values == 1).sum()
                                ),
                                "test_both_classes": bool(
                                    test_values.nunique() == 2
                                ),
                                "test_single_class": bool(
                                    len(test_scored) > 0
                                    and test_values.nunique() == 1
                                ),
                                "test_empty": bool(
                                    len(test_scored) == 0
                                ),
                            }
                        )

    anchors = pd.DataFrame(anchor_rows)
    cells = pd.DataFrame(cell_rows)
    tests = pd.DataFrame(test_rows)
    return anchors, cells, tests


def build_protocol_summary(cell_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [
        "repetition",
        "role",
        "task",
        "label_policy",
    ]
    for keys, subset in cell_frame.groupby(group_columns):
        repetition, role, task, policy = keys
        rows.append(
            {
                "repetition": repetition,
                "role": role,
                "task": task,
                "label_policy": policy,
                "outer_cells": int(len(subset)),
                "source_rows_min": int(
                    subset["source_rows"].min()
                ),
                "source_rows_median": float(
                    subset["source_rows"].median()
                ),
                "source_scored_rows_min": int(
                    subset["source_scored_rows"].min()
                ),
                "source_low_min": int(
                    subset["source_low"].min()
                ),
                "source_high_min": int(
                    subset["source_high"].min()
                ),
                "all_source_cells_both_classes": bool(
                    subset["source_both_classes"].all()
                ),
                "eligible_donors_min": int(
                    subset["donor_min"].min()
                ),
                "eligible_donors_p10_min": float(
                    subset["donor_p10"].min()
                ),
                "eligible_donors_median_min": float(
                    subset["donor_median"].min()
                ),
                "eligible_donors_max": int(
                    subset["donor_max"].max()
                ),
                "zero_donor_rate_max": float(
                    subset["zero_donor_rate"].max()
                ),
                "below_5_donor_rate_max": float(
                    subset["below_5_rate"].max()
                ),
                "below_20_donor_rate_max": float(
                    subset["below_20_rate"].max()
                ),
                "unique_donor_subjects_min": int(
                    subset["unique_subject_min"].min()
                ),
                "unique_donor_videos_min": int(
                    subset["unique_video_min"].min()
                ),
                "unique_donor_quadrants_min": int(
                    subset["unique_quadrant_min"].min()
                ),
                "cells_with_any_zero_donor_anchor": int(
                    (subset["zero_donor_rate"] > 0).sum()
                ),
                "cells_with_any_below_5_anchor": int(
                    (subset["below_5_rate"] > 0).sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(group_columns)


def build_inner_joint_audit(
    manifest: pd.DataFrame,
    assignments: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for repetition in EXPECTED_REPETITIONS:
        participant_map, video_map = assignment_maps(
            assignments,
            repetition,
        )
        participant_fold = manifest["participant_id"].map(
            participant_map
        )
        video_fold = manifest["video_name"].map(video_map)

        for held_subject_fold in EXPECTED_FOLDS:
            for held_video_fold in EXPECTED_FOLDS:
                source_subject_folds = [
                    fold
                    for fold in EXPECTED_FOLDS
                    if fold != held_subject_fold
                ]
                source_video_folds = [
                    fold
                    for fold in EXPECTED_FOLDS
                    if fold != held_video_fold
                ]
                outer_cell = (
                    f"R{repetition:02d}_S{held_subject_fold}"
                    f"_V{held_video_fold}"
                )

                for train_subject_fold in source_subject_folds:
                    validation_subject_fold = next(
                        fold
                        for fold in source_subject_folds
                        if fold != train_subject_fold
                    )
                    for train_video_fold in source_video_folds:
                        validation_video_fold = next(
                            fold
                            for fold in source_video_folds
                            if fold != train_video_fold
                        )
                        inner_id = (
                            f"{outer_cell}_train_S{train_subject_fold}"
                            f"_V{train_video_fold}"
                        )
                        inner_train = manifest[
                            (participant_fold == train_subject_fold)
                            & (video_fold == train_video_fold)
                        ].copy()
                        inner_validation = manifest[
                            (
                                participant_fold
                                == validation_subject_fold
                            )
                            & (
                                video_fold
                                == validation_video_fold
                            )
                        ].copy()

                        base = {
                            "repetition": repetition,
                            "role": (
                                "primary"
                                if repetition == 0
                                else "sensitivity"
                            ),
                            "outer_cell": outer_cell,
                            "inner_id": inner_id,
                            "held_subject_fold": held_subject_fold,
                            "held_video_fold": held_video_fold,
                            "train_subject_fold": (
                                train_subject_fold
                            ),
                            "train_video_fold": train_video_fold,
                            "validation_subject_fold": (
                                validation_subject_fold
                            ),
                            "validation_video_fold": (
                                validation_video_fold
                            ),
                            "inner_train_subjects": int(
                                inner_train[
                                    "participant_id"
                                ].nunique()
                            ),
                            "inner_train_videos": int(
                                inner_train[
                                    "video_name"
                                ].nunique()
                            ),
                            "inner_train_rows": int(
                                len(inner_train)
                            ),
                            "inner_validation_subjects": int(
                                inner_validation[
                                    "participant_id"
                                ].nunique()
                            ),
                            "inner_validation_videos": int(
                                inner_validation[
                                    "video_name"
                                ].nunique()
                            ),
                            "inner_validation_rows": int(
                                len(inner_validation)
                            ),
                        }

                        for task in TASKS:
                            for policy in POLICIES:
                                donors = pd.DataFrame(
                                    donor_rows_for_region(
                                        inner_train,
                                        task,
                                        policy,
                                        base,
                                    )
                                )
                                donor_summary = summarize_donors(
                                    donors
                                )

                                train_labels = pd.to_numeric(
                                    inner_train[
                                        f"{task}_{policy}"
                                    ],
                                    errors="coerce",
                                )
                                val_labels = pd.to_numeric(
                                    inner_validation[
                                        f"{task}_{policy}"
                                    ],
                                    errors="coerce",
                                )
                                train_scored = train_labels.dropna().astype(
                                    int
                                )
                                val_scored = val_labels.dropna().astype(
                                    int
                                )

                                donor_operational = bool(
                                    donor_summary[
                                        "zero_donor_rate"
                                    ]
                                    <= 0.05
                                    and donor_summary[
                                        "donor_min"
                                    ]
                                    >= 1
                                )
                                rows.append(
                                    {
                                        **base,
                                        "task": task,
                                        "label_policy": policy,
                                        "inner_train_scored": int(
                                            len(train_scored)
                                        ),
                                        "inner_train_low": int(
                                            (train_scored == 0).sum()
                                        ),
                                        "inner_train_high": int(
                                            (train_scored == 1).sum()
                                        ),
                                        "inner_train_both_classes": bool(
                                            train_scored.nunique() == 2
                                        ),
                                        "inner_validation_scored": int(
                                            len(val_scored)
                                        ),
                                        "inner_validation_low": int(
                                            (val_scored == 0).sum()
                                        ),
                                        "inner_validation_high": int(
                                            (val_scored == 1).sum()
                                        ),
                                        "inner_validation_both_classes": bool(
                                            val_scored.nunique() == 2
                                        ),
                                        **{
                                            f"donor_{key}": value
                                            for key, value in (
                                                donor_summary.items()
                                            )
                                        },
                                        "donor_operational": (
                                            donor_operational
                                        ),
                                        "inner_joint_operational": bool(
                                            donor_operational
                                            and train_scored.nunique()
                                            == 2
                                            and val_scored.nunique()
                                            == 2
                                        ),
                                    }
                                )
    return pd.DataFrame(rows)


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [json_safe(item) for item in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def atomic_write_text(
    path: Path,
    text: str,
    overwrite: bool,
) -> None:
    if path.exists() and not overwrite:
        raise AuditError(
            f"Output exists: {path}. Use --overwrite to regenerate."
        )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def atomic_write_csv(
    frame: pd.DataFrame,
    path: Path,
    overwrite: bool,
    compression: str | None = None,
) -> None:
    if path.exists() and not overwrite:
        raise AuditError(
            f"Output exists: {path}. Use --overwrite to regenerate."
        )
    temporary = path.with_name(path.name + ".tmp")
    frame.to_csv(
        temporary,
        index=False,
        compression=compression,
    )
    os.replace(temporary, path)


def markdown_table(
    rows: Iterable[Iterable[Any]],
    headers: list[str],
) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "\\|")
                for value in row
            )
            + " |"
        )
    return lines


def determine_verdict(
    raw_windows: pd.DataFrame,
    protocol_summary: pd.DataFrame,
    inner: pd.DataFrame,
    tests: pd.DataFrame,
    shortcut_payload: dict[str, Any],
) -> dict[str, Any]:
    primary = protocol_summary[
        (protocol_summary["repetition"] == 0)
        & (
            protocol_summary["label_policy"]
            == "discard_midpoint"
        )
    ].copy()
    all_primary_task_rows = len(primary) == 2

    raw_all_constructible = bool(
        len(raw_windows) == 90
        and raw_windows["minimum_two_windows"].all()
    )
    raw_window_min = int(
        raw_windows["paired_valid_5s_windows"].min()
    )

    primary_zero_rate = float(
        primary["zero_donor_rate_max"].max()
    )
    primary_min_donors = int(
        primary["eligible_donors_min"].min()
    )
    primary_below_5_rate = float(
        primary["below_5_donor_rate_max"].max()
    )
    primary_unique_subjects_min = int(
        primary["unique_donor_subjects_min"].min()
    )
    primary_unique_videos_min = int(
        primary["unique_donor_videos_min"].min()
    )

    all_reps_primary_policy = protocol_summary[
        protocol_summary["label_policy"]
        == "discard_midpoint"
    ]
    all_reps_zero_rate = float(
        all_reps_primary_policy["zero_donor_rate_max"].max()
    )
    all_reps_min_donors = int(
        all_reps_primary_policy["eligible_donors_min"].min()
    )

    inner_primary = inner[
        inner["label_policy"] == "discard_midpoint"
    ].copy()
    inner_operational_rate = float(
        inner_primary["inner_joint_operational"].mean()
    )
    primary_inner = inner_primary[
        inner_primary["repetition"] == 0
    ]
    primary_inner_operational_rate = float(
        primary_inner["inner_joint_operational"].mean()
    )

    primary_tests = tests[
        (tests["repetition"] == 0)
        & (tests["label_policy"] == "discard_midpoint")
    ]
    primary_single_class_cells = int(
        primary_tests["test_single_class"].sum()
    )
    primary_empty_cells = int(
        primary_tests["test_empty"].sum()
    )
    minimum_primary_test_scored = int(
        primary_tests["test_scored_rows"].min()
    )

    shortcut_decision = str(
        shortcut_payload.get(
            "decision",
            "UNAVAILABLE",
        )
    )
    shortcut_ok = (
        shortcut_decision
        == "PROCEED_WITH_STANDARD_SHORTCUT_GATE"
    )

    red_reasons: list[str] = []
    yellow_reasons: list[str] = []

    if not raw_all_constructible:
        red_reasons.append(
            "At least one retained physical trial cannot provide two "
            "paired valid 5 s Raw-XDF windows."
        )
    if not all_primary_task_rows:
        red_reasons.append(
            "Primary donor summary is incomplete."
        )
    if primary_zero_rate > 0.05:
        red_reasons.append(
            "Primary donor failure exceeds the predeclared 5% kill threshold."
        )
    if primary_min_donors < 1:
        red_reasons.append(
            "At least one primary source anchor has no legal PM-SSI donor."
        )
    if primary_empty_cells > 0:
        red_reasons.append(
            "At least one primary joint test cell is empty after masking."
        )
    if not shortcut_ok:
        red_reasons.append(
            "Shortcut/null gate has not cleared."
        )

    if primary_below_5_rate > 0:
        yellow_reasons.append(
            "Some primary anchors have fewer than five legal donors."
        )
    if primary_unique_subjects_min < 3:
        yellow_reasons.append(
            "Some primary anchors have fewer than three donor subjects."
        )
    if primary_unique_videos_min < 3:
        yellow_reasons.append(
            "Some primary anchors have fewer than three donor exact videos."
        )
    if all_reps_zero_rate > 0:
        yellow_reasons.append(
            "At least one sensitivity repetition has a zero-donor anchor."
        )
    if all_reps_min_donors < 5:
        yellow_reasons.append(
            "Sensitivity repetitions do not maintain a five-donor minimum."
        )
    if primary_inner_operational_rate < 0.80:
        yellow_reasons.append(
            "Leakage-safe primary inner-joint training/validation is "
            "operational in fewer than 80% of configurations."
        )
    if inner_operational_rate < 0.80:
        yellow_reasons.append(
            "Across frozen repetitions, inner-joint model-selection "
            "capacity is fragile."
        )
    if primary_single_class_cells > 0:
        yellow_reasons.append(
            "Primary test contains task-specific single-class cells; "
            "only pooled-repetition metrics are valid."
        )
    if minimum_primary_test_scored < 5:
        yellow_reasons.append(
            "At least one primary task-cell has fewer than five scored trials."
        )
    yellow_reasons.extend(
        [
            "Only 24 participants and 90 emotional physical trials are "
            "available in the strict paired cohort.",
            "The participant-by-exact-video graph is sparse and includes "
            "singleton-supported videos.",
            "Exact video is highly informative for Valence in diagnostic "
            "seen-video regions, so no stimulus-removal claim is allowed.",
            "Raw XDF does not contain Fz. The verified official mapping is "
            "F3->FP1, S2->FP2, S3->C3, S4->C4, S5->LE, "
            "S6->EOG1, S7->EOG2. The paper must report four scalp EEG "
            "channels, one left-ear reference, and two EOG channels rather "
            "than five scalp channels including Fz.",
        ]
    )

    if red_reasons:
        color = "RED"
        role = "NOT_SUITABLE_FOR_PM_SSI_DG_PAPER_1"
    else:
        green_conditions = bool(
            primary_zero_rate == 0
            and primary_min_donors >= 5
            and primary_below_5_rate == 0
            and primary_unique_subjects_min >= 3
            and primary_unique_videos_min >= 3
            and all_reps_zero_rate == 0
            and all_reps_min_donors >= 5
            and primary_inner_operational_rate >= 0.80
            and inner_operational_rate >= 0.80
            and primary_single_class_cells == 0
            and minimum_primary_test_scored >= 5
            and raw_window_min >= 2
        )
        if green_conditions:
            color = "GREEN"
            role = "APPROVED_AS_THIRD_PAPER_1_DATASET"
        else:
            color = "YELLOW"
            role = "SECONDARY_EXTERNAL_VR_STRESS_TEST_ONLY"

    return {
        "verdict_color": color,
        "recommended_role": role,
        "raw_all_constructible": raw_all_constructible,
        "raw_min_valid_5s_windows_per_trial": raw_window_min,
        "primary_max_zero_donor_rate": primary_zero_rate,
        "primary_min_legal_donors": primary_min_donors,
        "primary_max_below_5_donor_rate": primary_below_5_rate,
        "primary_min_unique_donor_subjects": (
            primary_unique_subjects_min
        ),
        "primary_min_unique_donor_videos": (
            primary_unique_videos_min
        ),
        "all_repetitions_max_zero_donor_rate": (
            all_reps_zero_rate
        ),
        "all_repetitions_min_legal_donors": (
            all_reps_min_donors
        ),
        "primary_inner_joint_operational_rate": (
            primary_inner_operational_rate
        ),
        "all_repetitions_inner_joint_operational_rate": (
            inner_operational_rate
        ),
        "primary_single_class_task_cells": (
            primary_single_class_cells
        ),
        "primary_empty_task_cells": primary_empty_cells,
        "primary_minimum_scored_test_trials": (
            minimum_primary_test_scored
        ),
        "shortcut_decision": shortcut_decision,
        "red_reasons": red_reasons,
        "yellow_reasons": yellow_reasons,
    }


def make_report(
    metadata: dict[str, Any],
    verdict: dict[str, Any],
    raw_windows: pd.DataFrame,
    raw_sessions: pd.DataFrame,
    protocol_summary: pd.DataFrame,
    inner: pd.DataFrame,
    tests: pd.DataFrame,
) -> str:
    lines: list[str] = [
        "# Final DEJA-VU Qualification Audit for PM-SSI-DG",
        "",
        f"Generated: `{metadata['generated_at_utc']}`",
        "",
        "No physiological model was trained. The audit uses the frozen "
        "Cohort B manifest, frozen repeated 3×3 Joint Subject–Exact-Video "
        "assignments, Raw XDF, and the previously frozen shortcut/null audit.",
        "",
        "Verified Raw-XDF EEG mapping: `F3->FP1, S2->FP2, S3->C3, "
        "S4->C4, S5->LE, S6->EOG1, S7->EOG2`; `TRG` is excluded. "
        "Fz is not present in the distributed raw descriptor or official map.",
        "",
        "## Final verdict",
        "",
        f"**{verdict['verdict_color']} — "
        f"{verdict['recommended_role']}**",
        "",
        "## Headline capacity",
        "",
    ]
    lines.extend(
        markdown_table(
            [
                [
                    "Retained paired trials",
                    len(raw_windows),
                ],
                [
                    "Minimum valid paired 5 s windows per trial",
                    verdict[
                        "raw_min_valid_5s_windows_per_trial"
                    ],
                ],
                [
                    "Primary minimum legal donors",
                    verdict["primary_min_legal_donors"],
                ],
                [
                    "Primary maximum zero-donor rate",
                    f"{verdict['primary_max_zero_donor_rate']:.4f}",
                ],
                [
                    "Primary maximum rate with <5 donors",
                    f"{verdict['primary_max_below_5_donor_rate']:.4f}",
                ],
                [
                    "Primary minimum unique donor subjects",
                    verdict[
                        "primary_min_unique_donor_subjects"
                    ],
                ],
                [
                    "Primary minimum unique donor exact videos",
                    verdict[
                        "primary_min_unique_donor_videos"
                    ],
                ],
                [
                    "Primary inner-joint operational rate",
                    f"{verdict['primary_inner_joint_operational_rate']:.4f}",
                ],
                [
                    "All-repetition inner-joint operational rate",
                    f"{verdict['all_repetitions_inner_joint_operational_rate']:.4f}",
                ],
                [
                    "Primary task-specific single-class cells",
                    verdict[
                        "primary_single_class_task_cells"
                    ],
                ],
                [
                    "Primary minimum scored test trials",
                    verdict[
                        "primary_minimum_scored_test_trials"
                    ],
                ],
                [
                    "Shortcut/null decision",
                    verdict["shortcut_decision"],
                ],
            ],
            ["Metric", "Value"],
        )
    )

    lines.extend(
        [
            "",
            "## Primary repetition donor support",
            "",
        ]
    )
    primary = protocol_summary[
        (protocol_summary["repetition"] == 0)
        & (
            protocol_summary["label_policy"]
            == "discard_midpoint"
        )
    ]
    donor_rows = []
    for row in primary.itertuples(index=False):
        donor_rows.append(
            [
                row.task,
                row.source_scored_rows_min,
                f"{row.source_low_min}/{row.source_high_min}",
                row.eligible_donors_min,
                f"{row.eligible_donors_p10_min:.1f}",
                f"{row.eligible_donors_median_min:.1f}",
                f"{row.zero_donor_rate_max:.4f}",
                f"{row.below_5_donor_rate_max:.4f}",
                row.unique_donor_subjects_min,
                row.unique_donor_videos_min,
                row.unique_donor_quadrants_min,
            ]
        )
    lines.extend(
        markdown_table(
            donor_rows,
            [
                "Task",
                "Min scored source trials",
                "Min Low/High",
                "Min donors",
                "Worst-cell donor P10",
                "Worst-cell donor median",
                "Max zero rate",
                "Max <5 rate",
                "Min donor subjects",
                "Min donor videos",
                "Min donor quadrants",
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Primary outer-test support",
            "",
        ]
    )
    primary_tests = tests[
        (tests["repetition"] == 0)
        & (
            tests["label_policy"]
            == "discard_midpoint"
        )
    ].sort_values(["task", "outer_cell"])
    test_rows = []
    for row in primary_tests.itertuples(index=False):
        test_rows.append(
            [
                row.outer_cell,
                row.task,
                row.test_rows,
                row.test_scored_rows,
                row.test_low,
                row.test_high,
                row.test_both_classes,
            ]
        )
    lines.extend(
        markdown_table(
            test_rows,
            [
                "Outer cell",
                "Task",
                "Raw test",
                "Scored",
                "Low",
                "High",
                "Both classes",
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Inner-joint model-selection capacity",
            "",
        ]
    )
    inner_primary = inner[
        inner["label_policy"] == "discard_midpoint"
    ]
    inner_rows = []
    for (repetition, task), subset in inner_primary.groupby(
        ["repetition", "task"]
    ):
        inner_rows.append(
            [
                repetition,
                task,
                len(subset),
                f"{subset['inner_joint_operational'].mean():.4f}",
                int(subset["inner_train_rows"].min()),
                int(subset["inner_validation_rows"].min()),
                int(subset["donor_donor_min"].min()),
                f"{subset['donor_zero_donor_rate'].max():.4f}",
            ]
        )
    lines.extend(
        markdown_table(
            inner_rows,
            [
                "Repetition",
                "Task",
                "Inner configs",
                "Operational rate",
                "Min train rows",
                "Min validation rows",
                "Min legal donors",
                "Max zero-donor rate",
            ],
        )
    )

    lines.extend(
        [
            "",
            "## Raw-XDF constructibility",
            "",
            f"- Raw scan mode: `{raw_windows['raw_scan_mode'].iloc[0]}`",
            f"- Sessions audited: `{raw_windows['participant_session_key'].nunique()}`",
            f"- Sessions with Raw-XDF loader errors: "
            f"`{0 if raw_sessions.empty else int((~raw_sessions['raw_loaded']).sum())}`",
            f"- Physical trials with at least two valid paired windows: "
            f"`{int(raw_windows['minimum_two_windows'].sum())} / {len(raw_windows)}`",
            f"- Valid paired-window count range: "
            f"`{int(raw_windows['paired_valid_5s_windows'].min())}` to "
            f"`{int(raw_windows['paired_valid_5s_windows'].max())}`",
            "",
            "## Decision reasons",
            "",
        ]
    )
    if verdict["red_reasons"]:
        lines.append("### RED triggers")
        lines.append("")
        for reason in verdict["red_reasons"]:
            lines.append(f"- {reason}")
        lines.append("")
    lines.append("### Restrictions and cautions")
    lines.append("")
    for reason in verdict["yellow_reasons"]:
        lines.append(f"- {reason}")

    lines.extend(
        [
            "",
            "## Permitted interpretation",
            "",
            "- PM-SSI may be described as paired provenance-preserving "
            "feature-statistics perturbation.",
            "- A different exact-video donor is available only when recorded "
            "by this audit; no same-video fallback is allowed.",
            "- Windows are computational views of one physical trial and are "
            "not independent samples.",
            "- The method cannot claim direct removal or causal "
            "disentanglement of stimulus identity.",
            "- If the verdict is YELLOW, all architecture and hyperparameters "
            "must be frozen on the main Paper-1 datasets before DEJA-VU is run.",
            "- Repetition 0 remains primary; repetitions 1–4 remain sensitivity.",
            "",
            "## Required outputs",
            "",
        ]
    )
    for name in OUTPUT_NAMES.values():
        lines.append(f"- `docs/{name}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    arguments = parse_args()
    repo = arguments.repo_root.resolve()
    data = arguments.data_root.resolve()
    docs = repo / "docs"
    manifests = repo / "manifests"
    folds = repo / "folds"
    raw_root = data / "extracted/dataset/DEJA-VU/raw"

    if not (repo / ".git").is_dir():
        raise AuditError(f"Repository not found: {repo}")
    if not raw_root.is_dir():
        raise AuditError(f"Raw XDF root not found: {raw_root}")

    manifest_path = manifests / "dejavu_cohort_b_primary_labels.csv"
    assignments_path = folds / "dejavu_joint_cv_repeated_assignments.csv"
    protocol_path = folds / "dejavu_joint_cv_protocol.json"
    shortcut_path = docs / "dejavu_shortcut_and_null_audit.json"

    for path in (
        manifest_path,
        assignments_path,
        protocol_path,
        shortcut_path,
    ):
        if not path.exists():
            raise AuditError(f"Required frozen artifact missing: {path}")

    manifest = prepare_manifest(pd.read_csv(manifest_path))
    assignments = validate_assignments(pd.read_csv(assignments_path))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    shortcut = json.loads(shortcut_path.read_text(encoding="utf-8"))

    if protocol.get("status") != "LOCK_WITH_CAPACITY_CAUTION":
        raise AuditError("Frozen protocol status mismatch")
    outer_protocol = protocol.get("outer_protocol", {})
    if (
        int(outer_protocol.get("subject_folds", -1)) != 3
        or int(outer_protocol.get("video_folds", -1)) != 3
        or int(outer_protocol.get("repetitions", -1)) != 5
    ):
        raise AuditError("Frozen protocol dimensions mismatch")

    print("===== RAW-XDF PAIRED-WINDOW AUDIT =====")
    raw_windows, raw_sessions = audit_raw_windows(
        manifest,
        raw_root,
        arguments.window_sec,
        arguments.skip_raw_xdf,
    )
    if len(raw_windows) != 90:
        raise AuditError(
            f"Expected 90 raw-window rows, found {len(raw_windows)}"
        )

    manifest = manifest.merge(
        raw_windows[
            [
                "presentation_id",
                "minimum_two_windows",
                "paired_valid_5s_windows",
            ]
        ],
        on="presentation_id",
        how="left",
        validate="one_to_one",
    )
    if manifest["minimum_two_windows"].isna().any():
        raise AuditError("Raw-window join produced missing rows")
    manifest["raw_window_constructible"] = (
        manifest["minimum_two_windows"].astype(bool)
    )

    print("===== OUTER DONOR AND TEST-SUPPORT AUDIT =====")
    anchors, cells, tests = build_outer_audit(
        manifest,
        assignments,
    )
    summary = build_protocol_summary(cells)

    print("===== INNER-JOINT SOURCE-VALIDATION AUDIT =====")
    inner = build_inner_joint_audit(
        manifest,
        assignments,
    )

    verdict = determine_verdict(
        raw_windows,
        summary,
        inner,
        tests,
        shortcut,
    )

    metadata = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo),
        "data_root": str(data),
        "git_branch": git_value(repo, "branch", "--show-current"),
        "git_head": git_value(repo, "rev-parse", "HEAD"),
        "git_status_before_outputs": git_value(
            repo,
            "status",
            "--short",
        ),
        "manifest_path": str(manifest_path),
        "manifest_sha256": sha256_file(manifest_path),
        "assignments_path": str(assignments_path),
        "assignments_sha256": sha256_file(assignments_path),
        "protocol_path": str(protocol_path),
        "protocol_sha256": sha256_file(protocol_path),
        "shortcut_path": str(shortcut_path),
        "shortcut_sha256": sha256_file(shortcut_path),
        "window_sec": float(arguments.window_sec),
        "raw_scan_skipped": bool(arguments.skip_raw_xdf),
        "anchor_rows": int(len(anchors)),
        "outer_cell_summary_rows": int(len(cells)),
        "outer_test_support_rows": int(len(tests)),
        "protocol_summary_rows": int(len(summary)),
        "inner_joint_rows": int(len(inner)),
    }

    output_paths = {
        key: docs / name
        for key, name in OUTPUT_NAMES.items()
    }
    docs.mkdir(parents=True, exist_ok=True)

    atomic_write_csv(
        raw_windows,
        output_paths["raw_windows"],
        arguments.overwrite,
    )
    atomic_write_csv(
        anchors,
        output_paths["anchor_support"],
        arguments.overwrite,
        compression="gzip",
    )
    atomic_write_csv(
        cells,
        output_paths["cell_support"],
        arguments.overwrite,
    )
    atomic_write_csv(
        summary,
        output_paths["protocol_summary"],
        arguments.overwrite,
    )
    atomic_write_csv(
        inner,
        output_paths["inner_support"],
        arguments.overwrite,
    )
    atomic_write_csv(
        tests,
        output_paths["test_support"],
        arguments.overwrite,
    )

    payload = {
        "metadata": metadata,
        "verdict": verdict,
        "raw_window_summary": {
            "rows": int(len(raw_windows)),
            "sessions": int(
                raw_windows[
                    "participant_session_key"
                ].nunique()
            ),
            "minimum_valid_windows": int(
                raw_windows[
                    "paired_valid_5s_windows"
                ].min()
            ),
            "median_valid_windows": float(
                raw_windows[
                    "paired_valid_5s_windows"
                ].median()
            ),
            "maximum_valid_windows": int(
                raw_windows[
                    "paired_valid_5s_windows"
                ].max()
            ),
            "all_trials_have_two_windows": bool(
                raw_windows["minimum_two_windows"].all()
            ),
        },
        "primary_donor_summary": summary[
            (summary["repetition"] == 0)
            & (
                summary["label_policy"]
                == "discard_midpoint"
            )
        ].to_dict(orient="records"),
        "all_protocol_donor_summary": summary.to_dict(
            orient="records"
        ),
        "outputs": {
            key: str(path)
            for key, path in output_paths.items()
        },
    }
    atomic_write_text(
        output_paths["report_json"],
        json.dumps(
            json_safe(payload),
            indent=2,
            sort_keys=True,
        ),
        arguments.overwrite,
    )
    report = make_report(
        metadata,
        verdict,
        raw_windows,
        raw_sessions,
        summary,
        inner,
        tests,
    )
    atomic_write_text(
        output_paths["report_md"],
        report,
        arguments.overwrite,
    )

    print()
    print("DEJA-VU PM-SSI-DG FINAL QUALIFICATION CHECKPOINT")
    print(f"Verdict: {verdict['verdict_color']}")
    print(f"Role: {verdict['recommended_role']}")
    print(
        "Raw paired windows: "
        f"min={verdict['raw_min_valid_5s_windows_per_trial']}, "
        f"all_constructible={verdict['raw_all_constructible']}"
    )
    print(
        "Primary donors: "
        f"min={verdict['primary_min_legal_donors']}, "
        f"max_zero_rate={verdict['primary_max_zero_donor_rate']:.4f}, "
        f"max_below5_rate="
        f"{verdict['primary_max_below_5_donor_rate']:.4f}"
    )
    print(
        "Primary inner-joint operational rate: "
        f"{verdict['primary_inner_joint_operational_rate']:.4f}"
    )
    print(
        "All-repetition inner-joint operational rate: "
        f"{verdict['all_repetitions_inner_joint_operational_rate']:.4f}"
    )
    print(
        "Primary single-class task-cells: "
        f"{verdict['primary_single_class_task_cells']}"
    )
    print(f"Report: {output_paths['report_md']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AuditError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
