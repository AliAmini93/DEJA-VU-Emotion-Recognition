# DEJA-VU Raw EMG Strict Signal-QC Refinement

Generated: `2026-07-13T15:27:15.350961+00:00`

This refinement adds saturation and long-plateau checks to the previous coverage/finite/flatline audit. Only sessions implicated by the earlier audit were reread from raw XDF.

## Revised capacity

| Unit | Total | Previous two-channel | Strict two-channel | Previous one-channel | Strict one-channel |
|---|---:|---:|---:|---:|---:|
| Presentations | 136 | 121 | 120 | 129 | 128 |
| Transitions | 102 | 90 | 90 | 96 | 96 |

## Failure rules

- finite fraction below `0.999`
- exact flatline
- one exact value occupies at least `95%` of finite samples
- one uninterrupted equal-value run occupies at least `50%` of finite samples

These are deterministic engineering-QC rules, not performance-selected thresholds.

## Non-passing implicated events

| Type | Unit | Session | Status | CH1 | CH2 |
|---|---|---|---|---|---|
| presentation | P012_S001_p1 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P012_S001_p2 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P012_S001_p3 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P012_S001_p4 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| transition | P012_S001_t1 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| transition | P012_S001_t2 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| transition | P012_S001_t3 | P012_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P015_S001_p1 | P015_S001 | FAIL | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| presentation | P015_S001_p2 | P015_S001 | FAIL | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| presentation | P015_S001_p3 | P015_S001 | FAIL | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| presentation | P015_S001_p4 | P015_S001 | FAIL | FAIL:LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| transition | P015_S001_t1 | P015_S001 | FAIL | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| transition | P015_S001_t2 | P015_S001 | FAIL | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| transition | P015_S001_t3 | P015_S001 | FAIL | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU |
| presentation | P019_S001_p1 | P019_S001 | FAIL | FAIL:NONFINITE | FAIL:NONFINITE |
| presentation | P019_S001_p2 | P019_S001 | FAIL | FAIL:NO_SAMPLES;NONFINITE | FAIL:NO_SAMPLES;NONFINITE |
| presentation | P019_S001_p3 | P019_S001 | FAIL | FAIL:NO_SAMPLES;NONFINITE | FAIL:NO_SAMPLES;NONFINITE |
| presentation | P019_S001_p4 | P019_S001 | FAIL | FAIL:NO_SAMPLES;NONFINITE | FAIL:NO_SAMPLES;NONFINITE |
| transition | P019_S001_t1 | P019_S001 | FAIL | FAIL:NO_SAMPLES;NONFINITE | FAIL:NO_SAMPLES;NONFINITE |
| transition | P019_S001_t2 | P019_S001 | FAIL | FAIL:NO_SAMPLES;NONFINITE | FAIL:NO_SAMPLES;NONFINITE |
| transition | P019_S001_t3 | P019_S001 | FAIL | FAIL:NO_SAMPLES;NONFINITE | FAIL:NO_SAMPLES;NONFINITE |
| presentation | P020_S001_p1 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P020_S001_p2 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P020_S001_p3 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| presentation | P020_S001_p4 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| transition | P020_S001_t1 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| transition | P020_S001_t2 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |
| transition | P020_S001_t3 | P020_S001 | ONE_CHANNEL_ONLY | FAIL:FLATLINE;SATURATED_MODE;LONG_PLATEAU | PASS:PASS |

## Decision boundary

- `strict_two_channel_emg_eligible=True` is the candidate requirement for standard two-channel EMG and paired EEG+EMG experiments.
- `strict_one_channel_emg_eligible=True` remains diagnostic only. A one-channel fallback is not authorized by this report.
- The official distributed EMG HDF5 groups remain unusable; future EMG must be re-derived from raw XDF indices identified by channel descriptors.

## Outputs

- `docs/dejavu_raw_emg_strict_signal_qc_events.csv`
- `docs/dejavu_raw_emg_strict_signal_qc.json`
- `manifests/dejavu_stimulus_presentation_emg_strict_qc.csv`
- `manifests/dejavu_transition_emg_strict_qc.csv`
