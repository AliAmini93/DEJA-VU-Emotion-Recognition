#!/usr/bin/env python
"""Forensic audit of the official code's raw-channel-to-modality mapping for
Shimmer-derived ECG/EMG/GSR streams, across all 34 raw XDF recordings.

Mirrors the exact index-selection logic in
extracted/official_code/code/lib_preprocessing_utils.py::read_and_process_xdf
(reproduced here, not re-derived) and checks it against each stream's real
channel descriptor. For EEG, the official code selects channels *via* the
descriptor (excluding "TRG" by label) — so EEG is checked for descriptor
self-consistency only. For the three Shimmer streams (ECG, EMG, GSR), the
official code slices `time_series[:, :N]`/`[:, 0]` **without ever reading
the descriptor** — this script is what actually checks the assumption.

Read-only. Loads raw sample arrays only for a bounded set of representative
sessions (for summary statistics) — never rewrites any file, never runs
filtering/ICA/segmentation.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np
import pyxdf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dejavu_lib import parse_participant_session_from_path  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_ROOT = Path("/mnt/HDD/AliWorks/DEJA-VU/extracted/dataset/DEJA-VU/raw")
DOCS_DIR = REPO_ROOT / "docs"

# Mirrors lib_preprocessing_utils.py exactly (not re-derived/guessed).
EEG_EXCLUDE = ["TRG"]
EEG_CHANNEL_MAP = {
    "F3": "FP1", "S2": "FP2", "S3": "C3", "S4": "C4",
    "S5": "LE", "S6": "EOG1", "S7": "EOG2",
}
SHIMMER_MAP = {"Shimmer_894F": "gsr", "Shimmer_BBBD": "emg", "Shimmer_BE1D": "ecg"}

# Precise (not substring-loose) identification of which descriptor labels are
# genuine modality signal channels, as opposed to status/accelerometer/battery
# channels that happen to share a prefix (e.g. "ECG_EMG_Status1" contains
# "ECG" as a substring but is not an ECG lead).
TRUE_SIGNAL_MATCHERS = {
    "ecg": lambda label: label.upper().startswith("ECG_") and "STATUS" not in label.upper(),
    "emg": lambda label: label.upper().startswith("EMG_") and "STATUS" not in label.upper(),
    "gsr": lambda label: "CONDUCTANCE" in label.upper(),
}

# The official code's hardcoded selection per modality (index slice, assigned labels).
CODE_SELECTION = {
    "ecg": {"slice": slice(0, 4), "assigned_labels": ["ECG_Lead_I", "ECG_Lead_II", "ECG_Lead_III", "ECG_Chest"]},
    "emg": {"slice": slice(0, 2), "assigned_labels": ["EMG_Zygomaticus", "EMG_Trapezius"]},
    "gsr": {"slice": slice(0, 1), "assigned_labels": ["GSR_Conductance"]},
}

REPRESENTATIVE_SESSIONS = [
    ("P001", "S001"),
    ("P017", "S002"),  # the P666-filename session
    ("P010", "S001"),
]


def get_channel_descriptor(stream) -> list[str]:
    try:
        channels = stream["info"]["desc"][0]["channels"][0]["channel"]
        return [ch["label"][0] for ch in channels]
    except (KeyError, IndexError, TypeError):
        return []


def get_channel_units(stream) -> list[str]:
    try:
        channels = stream["info"]["desc"][0]["channels"][0]["channel"]
        units = []
        for ch in channels:
            unit = ch.get("unit", [""])
            units.append(unit[0] if unit else "")
        return units
    except (KeyError, IndexError, TypeError):
        return []


def audit_one_file(xdf_path: Path, participant: str, session: str) -> list[dict]:
    rows = []
    streams, _ = pyxdf.load_xdf(str(xdf_path), verbose=False)
    for stream in streams:
        info = stream["info"]
        name = info.get("name", ["Unknown"])[0]
        stype = info.get("type", ["Unknown"])[0]
        srate = float(info.get("nominal_srate", ["0"])[0])
        labels = get_channel_descriptor(stream)
        units = get_channel_units(stream)

        if "DSI" in name:
            keep_indices = [i for i, lbl in enumerate(labels) if lbl not in EEG_EXCLUDE]
            selected_set = set(keep_indices)
            assigned = {i: EEG_CHANNEL_MAP.get(labels[i], labels[i]) for i in keep_indices}
        elif name in SHIMMER_MAP:
            modality = SHIMMER_MAP[name]
            sel = CODE_SELECTION[modality]
            selected_indices = list(range(*sel["slice"].indices(len(labels))))
            selected_set = set(selected_indices)
            assigned = {idx: sel["assigned_labels"][pos] for pos, idx in enumerate(selected_indices)}
        else:
            selected_set = set()
            assigned = {}

        modality = SHIMMER_MAP.get(name)
        for idx, label in enumerate(labels):
            is_selected = idx in selected_set
            assigned_label = assigned.get(idx, "")
            # metadata_consistent: is the descriptor label actually a genuine
            # signal channel for this modality (not status/accel/battery)?
            if is_selected:
                if "DSI" in name:
                    consistent = True  # descriptor-driven by construction
                elif modality:
                    consistent = TRUE_SIGNAL_MATCHERS[modality](label)
                else:
                    consistent = None
            else:
                consistent = None  # not selected, no claim made

            rows.append({
                "participant_id": participant,
                "session_id": session,
                "xdf_file": xdf_path.name,
                "stream_name": name,
                "stream_type": stype,
                "channel_index": idx,
                "channel_label": label,
                "channel_unit": units[idx] if idx < len(units) else "",
                "nominal_sampling_rate": srate,
                "official_code_selected": is_selected,
                "official_code_assigned_label": assigned_label,
                "metadata_consistent": consistent,
                "notes": "" if (consistent in (True, None)) else "MISMATCH: assigned label does not match true descriptor label at this index",
            })
    del streams
    return rows


def compute_stats(arr: np.ndarray) -> dict:
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "range": float(np.max(arr) - np.min(arr)),
        "n_unique_first_1000": int(len(np.unique(arr[:1000]))),
    }


def deep_dive_session(xdf_path: Path, participant: str, session: str) -> dict:
    streams, _ = pyxdf.load_xdf(str(xdf_path), verbose=False)
    result = {"participant": participant, "session": session, "streams": {}}
    for stream in streams:
        name = stream["info"].get("name", ["Unknown"])[0]
        if name not in SHIMMER_MAP:
            continue
        modality = SHIMMER_MAP[name]
        labels = get_channel_descriptor(stream)
        ts = stream["time_series"]
        sel = CODE_SELECTION[modality]
        selected_indices = list(range(*sel["slice"].indices(len(labels))))

        # Find true indices for the modality's real signal (precise matcher,
        # not loose prefix substring - see TRUE_SIGNAL_MATCHERS).
        true_indices = [i for i, lbl in enumerate(labels) if TRUE_SIGNAL_MATCHERS[modality](lbl)]

        stream_result = {
            "all_labels": labels,
            "code_selected_indices": selected_indices,
            "code_selected_labels": [labels[i] for i in selected_indices],
            "true_signal_indices_by_label": true_indices,
            "true_signal_labels": [labels[i] for i in true_indices],
            "code_selection_matches_true_signal": set(selected_indices) == set(true_indices) if true_indices else None,
            "stats_at_code_selected_indices": {labels[i]: compute_stats(ts[:, i]) for i in selected_indices},
            "stats_at_true_signal_indices": {labels[i]: compute_stats(ts[:, i]) for i in true_indices},
        }
        result["streams"][name] = stream_result
    del streams
    return result


def classify_modality(modality: str, all_rows: list[dict]) -> str:
    relevant = [r for r in all_rows if r["official_code_selected"] and r["stream_name"] in
                {"ecg": "Shimmer_BE1D", "emg": "Shimmer_BBBD", "gsr": "Shimmer_894F"}.get(modality, "")]
    if not relevant:
        return "UNRESOLVED"
    n_consistent = sum(1 for r in relevant if r["metadata_consistent"] is True)
    n_total = len(relevant)
    if n_consistent == n_total:
        return f"{modality.upper()}_MAPPING_VERIFIED"
    if n_consistent == 0:
        return f"{modality.upper()}_MAPPING_INCORRECT"
    return "UNRESOLVED"


def main() -> int:
    xdf_files = sorted(DATASET_ROOT.rglob("*.xdf"))
    print(f"found {len(xdf_files)} raw XDF files")

    all_rows = []
    for xdf_path in xdf_files:
        ident = parse_participant_session_from_path(str(xdf_path))
        participant = ident["subject"] or "UNKNOWN"
        session = ident["session"] or "UNKNOWN"
        print(f"  auditing {participant}/{session}: {xdf_path.name}")
        try:
            rows = audit_one_file(xdf_path, participant, session)
            all_rows.extend(rows)
        except Exception as exc:
            print(f"    WARNING: failed to audit {xdf_path}: {exc}", file=sys.stderr)

    with open(DOCS_DIR / "dejavu_raw_channel_mapping_by_session.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    print(f"wrote {len(all_rows)} rows to docs/dejavu_raw_channel_mapping_by_session.csv")

    # EEG classification: check descriptor-driven consistency (always True by construction,
    # but confirm no exceptions were recorded).
    eeg_rows = [r for r in all_rows if r["stream_name"] == "DSI_FLEX" and r["official_code_selected"]]
    eeg_ok = all(r["metadata_consistent"] is True for r in eeg_rows)
    eeg_classification = "EEG_MAPPING_VERIFIED" if eeg_ok else "UNRESOLVED"

    emg_classification = classify_modality("emg", all_rows)
    ecg_classification = classify_modality("ecg", all_rows)
    gsr_classification = classify_modality("gsr", all_rows)

    print(f"\nEEG: {eeg_classification}")
    print(f"EMG: {emg_classification}")
    print(f"ECG: {ecg_classification}")
    print(f"GSR: {gsr_classification}")

    deep_dives = []
    for participant, session in REPRESENTATIVE_SESSIONS:
        matches = [p for p in xdf_files if f"sub-{participant}" in str(p) and f"ses-{session}" in str(p)]
        if not matches:
            print(f"  no XDF found for {participant}/{session}, skipping deep dive")
            continue
        print(f"  deep-diving {participant}/{session}: {matches[0].name}")
        deep_dives.append(deep_dive_session(matches[0], participant, session))

    summary = {
        "total_xdf_files_audited": len(xdf_files),
        "total_channel_rows": len(all_rows),
        "classification": {
            "EEG": eeg_classification,
            "EMG": emg_classification,
            "ECG": ecg_classification,
            "GSR": gsr_classification,
        },
        "deep_dive_sessions": deep_dives,
    }
    with open(DOCS_DIR / "dejavu_raw_channel_mapping_audit.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("\nwrote docs/dejavu_raw_channel_mapping_audit.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
