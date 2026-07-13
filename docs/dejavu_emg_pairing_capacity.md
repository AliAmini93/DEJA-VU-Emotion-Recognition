# DEJA-VU Raw EMG Pairing-Capacity Audit

Generated: `2026-07-13T15:24:11.835059+00:00`

This is a read-only event-level audit using the true EMG channels resolved from raw XDF descriptors. No filtering, resampling, segmentation output, or training was performed.

## Capacity

| Unit | Total | Strict two-channel EMG eligible | At least one EMG channel eligible |
|---|---:|---:|---:|
| Stimulus presentations | 136 | 121 | 129 |
| Transition intervals | 102 | 90 | 96 |

Strict eligibility requires full timestamp/sample coverage, at least 99.9% finite samples in each true EMG channel, and no exact flatline in either channel.

## Problematic sessions

| Participant-session | Status | EMG/EEG duration ratio | EMG end relative to EEG (s) |
|---|---|---:|---:|
| P015_S001 | CH2_FLATLINE | 1.001518429450921 | 1159.1394645247128 |
| P019_S001 | CH1_NONFINITE;CH2_NONFINITE;SHORT_EMG_COVERAGE | 0.08807898460788129 | 103.74831617239397 |
| P020_S001 | CH1_FLATLINE | 1.0000743741414155 | 1256.2052142289467 |

## Interpretation

- Use `raw_emg_two_channel_eligible=True` for the strict paired EEG+EMG dataset.
- `raw_emg_one_channel_eligible=True` is reported only as a diagnostic salvage option; it is not automatically authorized as a modeling policy.
- The official distributed EMG HDF5 groups remain invalid because they contain hard-coded columns 0–1 rather than the descriptor-confirmed true EMG channels.
- The enriched manifests do not replace the original presentation and transition manifests.

## Outputs

- `docs/dejavu_raw_emg_eligibility_by_session.csv`
- `docs/dejavu_raw_emg_exception_channel_forensics.csv`
- `manifests/dejavu_stimulus_presentation_emg_eligibility.csv`
- `manifests/dejavu_transition_emg_eligibility.csv`
- `docs/dejavu_emg_pairing_capacity.json`
