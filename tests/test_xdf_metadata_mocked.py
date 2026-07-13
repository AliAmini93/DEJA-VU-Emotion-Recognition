"""Tests for audit_xdf_file() in scripts/01_audit_dejavu_dataset.py using a
mocked pyxdf.load_xdf — pyxdf has no writer API, so a real minimal XDF fixture
isn't practical; the reader is mocked with a small, realistic in-memory
stream structure instead (per instructions: "using a small fixture or mocked
reader")."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "audit_dejavu_dataset", SCRIPTS_DIR / "01_audit_dejavu_dataset.py"
)
audit_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit_module)


def make_mock_stream(name, stype, srate, channel_labels, n_samples, t_start=0.0):
    return {
        "info": {
            "name": [name],
            "type": [stype],
            "nominal_srate": [str(srate)],
            "channel_count": [str(len(channel_labels))],
            "desc": [{"channels": [{"channel": [{"label": [lbl]} for lbl in channel_labels]}]}],
        },
        "time_series": np.zeros((n_samples, len(channel_labels))),
        "time_stamps": np.linspace(t_start, t_start + n_samples / srate, n_samples) if n_samples else np.array([]),
    }


def test_audit_xdf_file_extracts_stream_metadata(tmp_path, monkeypatch):
    mock_streams = [
        make_mock_stream("DSI_FLEX", "EEG", 300.0, ["F3", "S2", "S3", "S4", "S5", "S6", "S7", "TRG"], 3000),
        make_mock_stream("Shimmer_BE1D", "Sensor_Data", 512.0,
                          ["Accel_LN_X", "Accel_LN_Y", "Accel_LN_Z", "ECG_EMG_Status1",
                           "ECG_EMG_Status2", "ECG_LL-RA_24BIT", "ECG_LA-RA_24BIT",
                           "ECG_LL-LA_24BIT", "ECG_Vx-RL_24BIT"], 5120),
    ]

    def fake_load_xdf(path, verbose=False):
        return mock_streams, {}

    monkeypatch.setattr(audit_module.pyxdf, "load_xdf", fake_load_xdf)

    dummy_path = tmp_path / "fake.xdf"
    dummy_path.write_bytes(b"not a real xdf file")  # content irrelevant, load_xdf is mocked

    result = audit_module.audit_xdf_file(dummy_path)

    assert len(result["streams"]) == 2
    eeg = result["streams"][0]
    assert eeg["stream_name"] == "DSI_FLEX"
    assert eeg["channel_count"] == 8
    assert eeg["channel_labels"][:3] == ["F3", "S2", "S3"]
    assert eeg["nominal_srate"] == 300.0
    assert eeg["n_samples"] == 3000
    assert eeg["is_empty_or_malformed"] is False

    ecg = result["streams"][1]
    assert ecg["stream_name"] == "Shimmer_BE1D"
    assert ecg["channel_count"] == 9
    # Regression guard for the real discrepancy documented in
    # docs/dejavu_identity_conflict_audit.md: true ECG leads are NOT at
    # indices 0-3.
    assert ecg["channel_labels"][:4] == ["Accel_LN_X", "Accel_LN_Y", "Accel_LN_Z", "ECG_EMG_Status1"]
    assert "ECG_LL-RA_24BIT" in ecg["channel_labels"][4:]


def test_audit_xdf_file_detects_empty_stream(tmp_path, monkeypatch):
    mock_streams = [make_mock_stream("EmptyStream", "Sensor_Data", 100.0, ["ch1"], 0)]

    def fake_load_xdf(path, verbose=False):
        return mock_streams, {}

    monkeypatch.setattr(audit_module.pyxdf, "load_xdf", fake_load_xdf)
    dummy_path = tmp_path / "empty.xdf"
    dummy_path.write_bytes(b"placeholder")

    result = audit_module.audit_xdf_file(dummy_path)

    assert result["streams"][0]["is_empty_or_malformed"] is True
    assert result["streams"][0]["n_samples"] == 0
    assert result["streams"][0]["timestamp_start"] is None


def test_audit_xdf_file_duration_computation(tmp_path, monkeypatch):
    mock_streams = [make_mock_stream("DSI_FLEX", "EEG", 300.0, ["F3"], 300, t_start=10.0)]

    def fake_load_xdf(path, verbose=False):
        return mock_streams, {}

    monkeypatch.setattr(audit_module.pyxdf, "load_xdf", fake_load_xdf)
    dummy_path = tmp_path / "one_sec.xdf"
    dummy_path.write_bytes(b"placeholder")

    result = audit_module.audit_xdf_file(dummy_path)
    stream = result["streams"][0]
    assert stream["timestamp_start"] == 10.0
    assert round(stream["duration_sec"], 2) == 1.0
