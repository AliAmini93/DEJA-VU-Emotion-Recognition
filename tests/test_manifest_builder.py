"""Tests for scripts/02_build_dejavu_manifests.py against a small synthetic
database + segment-file tree (2 sessions: a normal one and the P666-filename
case) — not the real ~3.72 GiB dataset."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import h5py
import pandas as pd
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "build_dejavu_manifests", SCRIPTS_DIR / "02_build_dejavu_manifests.py"
)
manifests_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(manifests_module)


def make_synthetic_tables() -> dict[str, pd.DataFrame]:
    # Two sessions: P001/S001 (normal, 1 session) and P017/S002 (the P666
    # raw-filename case). Each session: baseline (D) + 3 quadrants (A,B,C).
    journey_rows = []
    videos_rows = []
    ratings_rows = []
    video_mappings_rows = [
        {"video_name": "Clouds", "source": "FilmStim", "emotion": "Neutral", "quadrant": "D", "length_mmss": "1:00", "length_sec": 60},
        {"video_name": "Vid_A", "source": "EmoStim", "emotion": "Fun", "quadrant": "A", "length_mmss": "2:00", "length_sec": 120},
        {"video_name": "Vid_B", "source": "EmoStim", "emotion": "Fear", "quadrant": "B", "length_mmss": "2:00", "length_sec": 120},
        {"video_name": "Vid_C", "source": "EmoStim", "emotion": "Sadness", "quadrant": "C", "length_mmss": "2:00", "length_sec": 120},
    ]

    for subject, session in [("P001", "S001"), ("P017", "S002")]:
        t = 0
        for order, (video_name, quadrant) in enumerate(
            [("Clouds", "D"), ("Vid_A", "A"), ("Vid_B", "B"), ("Vid_C", "C")], start=1
        ):
            journey_rows.append({"subject": subject, "session": session, "position": order,
                                  "video_name": video_name, "quadrant": quadrant, "video_order": order})
            videos_rows.append({"subject": subject, "session": session, "video_order": order,
                                 "video_name": video_name, "video_start_24": "", "time_abs": "", "time_rel": t})
            t += 100
            for rt in ("before", "after"):
                ratings_rows.append({"subject": subject, "session": session, "video_name": video_name,
                                      "quadrant": quadrant, "rating_time": rt,
                                      "rating_valence": 5, "rating_arousal": 5, "rating_dominance": 5})

    return {
        "journey": pd.DataFrame(journey_rows),
        "videos": pd.DataFrame(videos_rows),
        "video_mappings": pd.DataFrame(video_mappings_rows),
        "ratings": pd.DataFrame(ratings_rows),
        "session_metadata": pd.DataFrame(),
    }


def make_segment_file(path: Path, groups=("eeg", "emg", "ecg", "gsr")):
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as f:
        for g in groups:
            f.create_group(g)


@pytest.fixture
def patched_module(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    segments_root = tmp_path / "segments"
    monkeypatch.setattr(manifests_module, "RAW_ROOT", raw_root)
    monkeypatch.setattr(manifests_module, "SEGMENTS_ROOT", segments_root)

    # Normal session: real-looking xdf filename.
    normal_dir = raw_root / "sub-P001" / "ses-S001" / "eeg"
    normal_dir.mkdir(parents=True)
    (normal_dir / "sub-P001_ses-S001_task-Default_run-001_eeg.xdf").write_bytes(b"x")

    # P666 session: matches manifests_module.P666_SESSION / P666_RAW_FILENAME.
    p666_dir = raw_root / "sub-P017" / "ses-S002" / "eeg"
    p666_dir.mkdir(parents=True)
    (p666_dir / manifests_module.P666_RAW_FILENAME).write_bytes(b"x")

    for subject, session in [("P001", "S001"), ("P017", "S002")]:
        make_segment_file(segments_root / f"sub-{subject}" / f"{session}_neutral_baseline.h5")
        for q, pos in [("A", 2), ("B", 3), ("C", 4)]:
            make_segment_file(segments_root / f"sub-{subject}" / f"{session}_quadrant_{q}_pos{pos}.h5")
        for tt in ["D_to_A", "A_to_B", "B_to_C"]:
            make_segment_file(segments_root / f"sub-{subject}" / f"{session}_transition_{tt}_period.h5")

    return manifests_module


def test_presentation_manifest_row_count(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    # 2 sessions x 4 journey positions = 8
    assert len(presentations) == 8


def test_transition_manifest_row_count(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    transitions = patched_module.build_transition_manifest(tables, presentations)
    # 2 sessions x 3 adjacent gaps = 6
    assert len(transitions) == 6


def test_presentation_and_transition_counts_are_kept_separate(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    transitions = patched_module.build_transition_manifest(tables, presentations)
    # The two must never be merged into one ambiguous count.
    assert len(presentations) != len(transitions)
    assert set(presentations.columns) != set(transitions.columns)


def test_presentation_ids_are_deterministic_and_unique(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    assert presentations["presentation_id"].is_unique
    # Re-running with identical input must produce identical IDs.
    presentations2 = patched_module.build_stimulus_presentation_manifest(tables)
    assert list(presentations["presentation_id"]) == list(presentations2["presentation_id"])
    assert presentations.loc[presentations.participant_id == "P001", "presentation_id"].tolist() == [
        "P001_S001_p1", "P001_S001_p2", "P001_S001_p3", "P001_S001_p4"
    ]


def test_transition_ids_are_deterministic(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    transitions = patched_module.build_transition_manifest(tables, presentations)
    key_cols = ["participant_id", "session_id", "transition_position"]
    keys = transitions[key_cols].apply(tuple, axis=1)
    assert keys.is_unique
    transitions2 = patched_module.build_transition_manifest(tables, presentations)
    assert transitions["transition_type"].tolist() == transitions2["transition_type"].tolist()


def test_p666_identity_handled_as_p017_s002(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    p666_rows = presentations[presentations.participant_id == "P017"]
    assert (p666_rows["identity_conflict_flag"]).all()
    assert (p666_rows["raw_xdf_file"] == manifests_module.P666_RAW_FILENAME).all()
    assert (p666_rows["session_id"] == "S002").all()


def test_normal_session_has_no_identity_conflict(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    normal_rows = presentations[presentations.participant_id == "P001"]
    assert not normal_rows["identity_conflict_flag"].any()


def test_database_to_segment_join_finds_real_files(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    assert presentations["segment_available"].all()
    assert presentations["segment_valid"].all()  # all 4 modality groups present


def test_participant_session_nesting_key(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    assert set(presentations["participant_session_key"]) == {"P001_S001", "P017_S002"}


def test_baseline_flagged_correctly(patched_module):
    tables = make_synthetic_tables()
    presentations = patched_module.build_stimulus_presentation_manifest(tables)
    baseline = presentations[presentations.chronological_position == 1]
    assert (baseline["is_baseline"]).all()
    assert not (baseline["is_emotional_stimulus"]).any()


def test_missing_segment_is_reported_not_fabricated(patched_module, tmp_path):
    tables = make_synthetic_tables()
    # Remove one segment file to simulate a genuine gap (like the real
    # P019/S001 EMG sensor failure).
    missing_path = manifests_module.SEGMENTS_ROOT / "sub-P001" / "S001_neutral_baseline.h5"
    missing_path.unlink()

    presentations = manifests_module.build_stimulus_presentation_manifest(tables)
    row = presentations[(presentations.participant_id == "P001") & (presentations.chronological_position == 1)].iloc[0]
    assert bool(row["segment_available"]) is False
    assert bool(row["segment_valid"]) is False
    assert row["segment_file"] == ""
