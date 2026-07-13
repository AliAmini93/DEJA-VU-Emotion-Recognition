"""Tests for scripts/01_audit_dejavu_channel_mapping.py — the forensic
ECG/EMG/GSR channel-descriptor-vs-code-selection audit — using mocked
pyxdf streams built from the real observed channel layouts (no real XDF
file needed)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

_spec = importlib.util.spec_from_file_location(
    "audit_channel_mapping", SCRIPTS_DIR / "01_audit_dejavu_channel_mapping.py"
)
mapping_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mapping_module)


def make_mock_stream(name, channel_labels, n_samples=100):
    return {
        "info": {
            "name": [name],
            "type": ["Sensor_Data"],
            "nominal_srate": ["512.0"],
            "desc": [{"channels": [{"channel": [{"label": [lbl]} for lbl in channel_labels]}]}],
        },
        "time_series": np.random.RandomState(0).randn(n_samples, len(channel_labels)),
    }


# --- TRUE_SIGNAL_MATCHERS precision (the bug that was found and fixed) ---

def test_ecg_matcher_excludes_status_channel():
    assert mapping_module.TRUE_SIGNAL_MATCHERS["ecg"]("ECG_EMG_Status1") is False


def test_ecg_matcher_accepts_real_lead():
    assert mapping_module.TRUE_SIGNAL_MATCHERS["ecg"]("ECG_LL-RA_24BIT") is True


def test_emg_matcher_excludes_status_channel():
    assert mapping_module.TRUE_SIGNAL_MATCHERS["emg"]("ECG_EMG_Status1") is False


def test_emg_matcher_accepts_real_channel():
    assert mapping_module.TRUE_SIGNAL_MATCHERS["emg"]("EMG_CH1_24BIT") is True


def test_gsr_matcher_finds_conductance_only():
    assert mapping_module.TRUE_SIGNAL_MATCHERS["gsr"]("GSR_Skin_Conductance") is True
    assert mapping_module.TRUE_SIGNAL_MATCHERS["gsr"]("GSR_Skin_Resistance") is False
    assert mapping_module.TRUE_SIGNAL_MATCHERS["gsr"]("Accel_LN_X") is False


# --- audit_one_file: real observed channel layouts ---

def test_ecg_stream_flags_code_selected_status_as_inconsistent(tmp_path, monkeypatch):
    labels = ["Accel_LN_X", "Accel_LN_Y", "Accel_LN_Z", "ECG_EMG_Status1",
              "ECG_EMG_Status2", "ECG_LL-RA_24BIT", "ECG_LA-RA_24BIT",
              "ECG_LL-LA_24BIT", "ECG_Vx-RL_24BIT"]
    stream = make_mock_stream("Shimmer_BE1D", labels)

    def fake_load_xdf(path, verbose=False):
        return [stream], {}

    monkeypatch.setattr(mapping_module.pyxdf, "load_xdf", fake_load_xdf)
    dummy = tmp_path / "fake.xdf"
    dummy.write_bytes(b"x")

    rows = mapping_module.audit_one_file(dummy, "P001", "S001")
    selected = [r for r in rows if r["official_code_selected"]]
    assert len(selected) == 4  # code slices [:4]
    assert all(r["metadata_consistent"] is False for r in selected)
    assert [r["channel_label"] for r in selected] == ["Accel_LN_X", "Accel_LN_Y", "Accel_LN_Z", "ECG_EMG_Status1"]


def test_gsr_stream_flags_accelerometer_as_inconsistent(tmp_path, monkeypatch):
    labels = ["Accel_LN_X", "Accel_LN_Y", "Accel_LN_Z", "GSR_Skin_Resistance",
              "GSR_Skin_Conductance", "GSR_Range", "PPG_A13"]
    stream = make_mock_stream("Shimmer_894F", labels)

    def fake_load_xdf(path, verbose=False):
        return [stream], {}

    monkeypatch.setattr(mapping_module.pyxdf, "load_xdf", fake_load_xdf)
    dummy = tmp_path / "fake.xdf"
    dummy.write_bytes(b"x")

    rows = mapping_module.audit_one_file(dummy, "P001", "S001")
    selected = [r for r in rows if r["official_code_selected"]]
    assert len(selected) == 1
    assert selected[0]["channel_label"] == "Accel_LN_X"
    assert selected[0]["metadata_consistent"] is False


def test_eeg_stream_is_descriptor_driven_and_consistent(tmp_path, monkeypatch):
    labels = ["F3", "S2", "S3", "S4", "S5", "S6", "S7", "TRG"]
    stream = make_mock_stream("DSI_FLEX", labels)

    def fake_load_xdf(path, verbose=False):
        return [stream], {}

    monkeypatch.setattr(mapping_module.pyxdf, "load_xdf", fake_load_xdf)
    dummy = tmp_path / "fake.xdf"
    dummy.write_bytes(b"x")

    rows = mapping_module.audit_one_file(dummy, "P001", "S001")
    selected = [r for r in rows if r["official_code_selected"]]
    assert len(selected) == 7  # TRG excluded
    assert all(r["metadata_consistent"] is True for r in selected)
    assert "TRG" not in [r["channel_label"] for r in selected]


def test_hypothetical_correctly_ordered_ecg_stream_is_consistent(tmp_path, monkeypatch):
    """If a stream's descriptor genuinely had ECG leads at indices 0-3 (not
    the case in the real dataset), the audit must report it as consistent -
    proving the check isn't hardcoded to always fail."""
    labels = ["ECG_LL-RA_24BIT", "ECG_LA-RA_24BIT", "ECG_LL-LA_24BIT", "ECG_Vx-RL_24BIT"]
    stream = make_mock_stream("Shimmer_BE1D", labels)

    def fake_load_xdf(path, verbose=False):
        return [stream], {}

    monkeypatch.setattr(mapping_module.pyxdf, "load_xdf", fake_load_xdf)
    dummy = tmp_path / "fake.xdf"
    dummy.write_bytes(b"x")

    rows = mapping_module.audit_one_file(dummy, "P001", "S001")
    selected = [r for r in rows if r["official_code_selected"]]
    assert all(r["metadata_consistent"] is True for r in selected)


# --- classify_modality ---

def test_classify_modality_incorrect_when_zero_consistent():
    rows = [
        {"stream_name": "Shimmer_BE1D", "official_code_selected": True, "metadata_consistent": False},
        {"stream_name": "Shimmer_BE1D", "official_code_selected": True, "metadata_consistent": False},
    ]
    assert mapping_module.classify_modality("ecg", rows) == "ECG_MAPPING_INCORRECT"


def test_classify_modality_verified_when_all_consistent():
    rows = [
        {"stream_name": "Shimmer_BE1D", "official_code_selected": True, "metadata_consistent": True},
        {"stream_name": "Shimmer_BE1D", "official_code_selected": True, "metadata_consistent": True},
    ]
    assert mapping_module.classify_modality("ecg", rows) == "ECG_MAPPING_VERIFIED"


def test_classify_modality_unresolved_when_mixed():
    rows = [
        {"stream_name": "Shimmer_BE1D", "official_code_selected": True, "metadata_consistent": True},
        {"stream_name": "Shimmer_BE1D", "official_code_selected": True, "metadata_consistent": False},
    ]
    assert mapping_module.classify_modality("ecg", rows) == "UNRESOLVED"


def test_classify_modality_unresolved_when_no_data():
    assert mapping_module.classify_modality("ecg", []) == "UNRESOLVED"
