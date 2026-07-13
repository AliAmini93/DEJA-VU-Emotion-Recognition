#!/usr/bin/env python
"""Build the DEJA-VU stimulus-presentation and transition-interval manifests.

Every row is derived from the official SQLite database, the segment HDF5
files actually on disk, and the raw XDF file inventory — nothing is
generated to force a target count. 136 stimulus presentations and 102
transitions are *expected* (34 sessions x 4 journey positions, and 34 x 3
adjacent gaps respectively) but are reported as counted, not asserted.

Read-only against the dataset; writes only into manifests/.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dejavu_lib import parse_participant_session_from_path  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path("/mnt/HDD/AliWorks/DEJA-VU/extracted/dataset/DEJA-VU/deja_vu_database.db")
RAW_ROOT = Path("/mnt/HDD/AliWorks/DEJA-VU/extracted/dataset/DEJA-VU/raw")
SEGMENTS_ROOT = Path("/mnt/HDD/AliWorks/DEJA-VU/extracted/dataset/DEJA-VU/segments")
MANIFESTS_DIR = REPO_ROOT / "manifests"

P666_SESSION = ("P017", "S002")
P666_RAW_FILENAME = "sub-P666_ses-S001_task-Default_run-001_eeg.xdf"


def load_tables(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    tables = ["journey", "videos", "video_mappings", "ratings", "session_metadata"]
    return {t: pd.read_sql_query(f"SELECT * FROM {t}", conn) for t in tables}


def find_raw_xdf_file(subject: str, session: str) -> str:
    if (subject, session) == P666_SESSION:
        return P666_RAW_FILENAME
    folder = RAW_ROOT / f"sub-{subject}" / f"ses-{session}" / "eeg"
    if folder.exists():
        matches = list(folder.glob("*.xdf"))
        if matches:
            return matches[0].name
    return ""


def h5_group_presence(h5_path: Path) -> dict[str, bool]:
    if not h5_path.exists():
        return {"eeg": False, "emg": False, "ecg": False, "gsr": False}
    import h5py
    with h5py.File(h5_path, "r") as f:
        return {mod: (mod in f) for mod in ("eeg", "emg", "ecg", "gsr")}


def compute_session_timeline(videos_df: pd.DataFrame, video_mappings_df: pd.DataFrame,
                              subject: str, session: str) -> pd.DataFrame:
    """Mirrors lib_segment_metadata.py::get_video_timeline exactly: end_time
    of row N is the start_time (time_rel) of row N+1 in video_order sequence;
    the last row's end_time is a fallback (start + expected_duration)."""
    sess = videos_df[(videos_df.subject == subject) & (videos_df.session == session)].sort_values("video_order").reset_index(drop=True)
    sess["end_time"] = sess["time_rel"].shift(-1)
    sess["timeline_end_is_fallback"] = False
    if len(sess) and pd.isna(sess.loc[len(sess) - 1, "end_time"]):
        last_video_name = sess.loc[len(sess) - 1, "video_name"]
        vm = video_mappings_df[video_mappings_df.video_name == last_video_name]
        expected_dur = vm["length_sec"].iloc[0] if len(vm) else None
        if expected_dur is not None:
            sess.loc[len(sess) - 1, "end_time"] = sess.loc[len(sess) - 1, "time_rel"] + expected_dur
            sess.loc[len(sess) - 1, "timeline_end_is_fallback"] = True
    return sess


def build_stimulus_presentation_manifest(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    journey = tables["journey"]
    videos = tables["videos"]
    video_mappings = tables["video_mappings"]
    ratings = tables["ratings"]

    rows = []
    for (subject, session), sess_journey in journey.groupby(["subject", "session"]):
        timeline = compute_session_timeline(videos, video_mappings, subject, session)
        raw_xdf_file = find_raw_xdf_file(subject, session)
        identity_conflict = (subject, session) == P666_SESSION

        for _, jrow in sess_journey.sort_values("position").iterrows():
            position = int(jrow["position"])
            video_name = jrow["video_name"]
            quadrant = jrow["quadrant"]
            video_order = int(jrow["video_order"])

            tl_row = timeline[timeline.video_order == video_order]
            timeline_start = float(tl_row["time_rel"].iloc[0]) if len(tl_row) else None
            timeline_end = float(tl_row["end_time"].iloc[0]) if len(tl_row) else None
            fallback = bool(tl_row["timeline_end_is_fallback"].iloc[0]) if len(tl_row) else False
            timeline_duration = (timeline_end - timeline_start) if (timeline_start is not None and timeline_end is not None) else None

            vm = video_mappings[video_mappings.video_name == video_name]
            source = vm["source"].iloc[0] if len(vm) else ""
            emotion_name = vm["emotion"].iloc[0] if len(vm) else ""
            stimulus_duration = float(vm["length_sec"].iloc[0]) if len(vm) else None
            canonical_quadrant = vm["quadrant"].iloc[0] if len(vm) else quadrant

            is_baseline = (position == 1)
            is_emotional = not is_baseline

            r = ratings[(ratings.subject == subject) & (ratings.session == session) & (ratings.video_name == video_name)]
            r_before = r[r.rating_time == "before"]
            r_after = r[r.rating_time == "after"]
            valence = float(r_after["rating_valence"].iloc[0]) if len(r_after) else (float(r_before["rating_valence"].iloc[0]) if len(r_before) else None)
            arousal = float(r_after["rating_arousal"].iloc[0]) if len(r_after) else (float(r_before["rating_arousal"].iloc[0]) if len(r_before) else None)
            dominance = float(r_after["rating_dominance"].iloc[0]) if len(r_after) else (float(r_before["rating_dominance"].iloc[0]) if len(r_before) else None)
            rating_policy_status = f"before={len(r_before)},after={len(r_after)}"

            if is_baseline:
                seg_filename = f"{session}_neutral_baseline.h5"
                segment_type = "neutral_baseline"
            else:
                seg_filename = f"{session}_quadrant_{quadrant}_pos{position}.h5"
                segment_type = "quadrant"
            seg_path = SEGMENTS_ROOT / f"sub-{subject}" / seg_filename
            segment_available = seg_path.exists()
            avail = h5_group_presence(seg_path) if segment_available else {"eeg": False, "emg": False, "ecg": False, "gsr": False}
            segment_valid = segment_available and all(avail.values())

            preprocessed_hdf5_file = f"clean_{subject}_{session}.h5"

            presentation_id = f"{subject}_{session}_p{position}"

            rows.append({
                "dataset": "DEJA-VU",
                "participant_id": subject,
                "session_id": session,
                "chronological_position": position,
                "video_order": video_order,
                "presentation_id": presentation_id,
                "video_name": video_name,
                "video_id": video_name.strip().lower().replace(" ", "_"),
                "content_id": f"{source}_{video_name}".strip().lower().replace(" ", "_") if source else video_name.strip().lower().replace(" ", "_"),
                "source": source,
                "canonical_quadrant": canonical_quadrant,
                "emotion_name": emotion_name,
                "stimulus_duration_sec": stimulus_duration,
                "timeline_start_sec": timeline_start,
                "timeline_end_sec": timeline_end,
                "timeline_duration_sec": timeline_duration,
                "timeline_end_is_fallback": fallback,
                "segment_file": seg_filename if segment_available else "",
                "segment_available": segment_available,
                "segment_valid": segment_valid,
                "segment_type": segment_type,
                "is_baseline": is_baseline,
                "is_emotional_stimulus": is_emotional,
                "valence_rating": valence,
                "arousal_rating": arousal,
                "dominance_rating": dominance,
                "valence_rating_count": len(r),
                "arousal_rating_count": len(r),
                "rating_policy_status": rating_policy_status,
                "eeg_available": avail["eeg"],
                "emg_available": avail["emg"],
                "ecg_available": avail["ecg"],
                "gsr_available": avail["gsr"],
                "raw_xdf_file": raw_xdf_file,
                "preprocessed_hdf5_file": preprocessed_hdf5_file,
                "participant_session_key": f"{subject}_{session}",
                "source_database_rows": f"journey:1;videos:{len(tl_row)};video_mappings:{len(vm)};ratings:{len(r)}",
                "identity_conflict_flag": identity_conflict,
                "notes": "P666 filename anomaly - see docs/dejavu_identity_conflict_audit.md" if identity_conflict else "",
            })
    return pd.DataFrame(rows)


def build_transition_manifest(tables: dict[str, pd.DataFrame], presentations: pd.DataFrame) -> pd.DataFrame:
    journey = tables["journey"]
    rows = []
    for (subject, session), sess_journey in journey.groupby(["subject", "session"]):
        sess_journey = sess_journey.sort_values("position").reset_index(drop=True)
        sess_presentations = presentations[(presentations.participant_id == subject) & (presentations.session_id == session)].set_index("chronological_position")

        for i in range(len(sess_journey) - 1):
            pos_from = sess_journey.iloc[i]
            pos_to = sess_journey.iloc[i + 1]
            p_from = sess_presentations.loc[int(pos_from["position"])]
            p_to = sess_presentations.loc[int(pos_to["position"])]

            transition_type = f"{pos_from['quadrant']}_to_{pos_to['quadrant']}"
            transition_start = p_from["timeline_end_sec"]
            transition_end = p_to["timeline_start_sec"]
            duration = (transition_end - transition_start) if (transition_start is not None and transition_end is not None) else None

            seg_filename = f"{session}_transition_{transition_type}_period.h5"
            seg_path = SEGMENTS_ROOT / f"sub-{subject}" / seg_filename
            segment_available = seg_path.exists()
            avail = h5_group_presence(seg_path) if segment_available else {"eeg": False, "emg": False, "ecg": False, "gsr": False}
            segment_valid = segment_available and all(avail.values())

            chron_verified = int(pos_to["video_order"]) > int(pos_from["video_order"])

            rows.append({
                "dataset": "DEJA-VU",
                "participant_id": subject,
                "session_id": session,
                "transition_position": i + 1,
                "previous_presentation_id": p_from["presentation_id"],
                "next_presentation_id": p_to["presentation_id"],
                "previous_video_name": p_from["video_name"],
                "next_video_name": p_to["video_name"],
                "previous_content_id": p_from["content_id"],
                "next_content_id": p_to["content_id"],
                "previous_quadrant": pos_from["quadrant"],
                "next_quadrant": pos_to["quadrant"],
                "transition_type": transition_type,
                "transition_start_sec": transition_start,
                "transition_end_sec": transition_end,
                "duration_sec": duration,
                "segment_file": seg_filename if segment_available else "",
                "segment_available": segment_available,
                "segment_valid": segment_valid,
                "eeg_available": avail["eeg"],
                "emg_available": avail["emg"],
                "ecg_available": avail["ecg"],
                "gsr_available": avail["gsr"],
                "chronological_order_verified": chron_verified,
                "notes": "",
            })
    return pd.DataFrame(rows)


def main() -> int:
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    tables = load_tables(conn)
    conn.close()

    presentations = build_stimulus_presentation_manifest(tables)
    print(f"stimulus presentation manifest: {len(presentations)} rows (expected candidate: 136)")
    presentations.to_csv(MANIFESTS_DIR / "dejavu_stimulus_presentation_manifest.csv", index=False)
    presentations.to_parquet(MANIFESTS_DIR / "dejavu_stimulus_presentation_manifest.parquet", index=False)

    transitions = build_transition_manifest(tables, presentations)
    print(f"transition manifest: {len(transitions)} rows (expected candidate: 102)")
    transitions.to_csv(MANIFESTS_DIR / "dejavu_transition_manifest.csv", index=False)
    transitions.to_parquet(MANIFESTS_DIR / "dejavu_transition_manifest.parquet", index=False)

    print("\nsegment_valid counts:")
    print("  presentations:", presentations["segment_valid"].sum(), "/", len(presentations))
    print("  transitions:", transitions["segment_valid"].sum(), "/", len(transitions))
    print("identity_conflict_flag rows:", presentations["identity_conflict_flag"].sum())

    return 0


if __name__ == "__main__":
    sys.exit(main())
