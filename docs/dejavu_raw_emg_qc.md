# DEJA-VU Raw EMG Availability and QC Audit

Generated: `2026-07-13T15:17:04.381611+00:00`

Read-only audit of descriptor-identified true EMG channels in raw XDF files. No filtering, resampling, segmentation, or training was performed.

## Headline results

| Metric | Value |
|---|---:|
| Raw XDF files discovered | 34 |
| Sessions passed | 31 |
| Sessions with warning/error | 3 |
| True EMG channel rows | 68 |
| True EMG channels with non-finite samples | 2 |
| True EMG channels constant/near-constant | 2 |
| Presentations with full raw-EMG coverage | 132 / 136 |
| Transitions with full raw-EMG coverage | 99 / 102 |

## Session-level exceptions

| Session | Status | EMG duration | EEG duration | End gap | Error |
|---|---|---:|---:|---:|---|
| P015_S001 | TRUE_EMG_CONSTANT | 1160.2751979259992 | 1158.5160730013886 | -0.6233915233242442 |  |
| P019_S001 | TRUE_EMG_NONFINITE;SHORT_EMG_COVERAGE | 103.71365389996208 | 1177.507374337758 | 1073.759058165364 |  |
| P020_S001 | TRUE_EMG_CONSTANT | 1256.1144766442012 | 1256.021061156178 | -0.1841530727688223 |  |

## Event intervals without full raw-EMG coverage

| Type | ID | Session | Start | End | Coverage | Reason |
|---|---|---|---:|---:|---:|---|
| presentation | P019_S001_p1 | P019_S001 | 32.0 | 216.0 | 0.3953 | BOUNDARY_NOT_COVERED;LOW_SAMPLE_COVERAGE |
| presentation | P019_S001_p2 | P019_S001 | 349.0 | 521.0 | 0.0000 | NO_OVERLAP;BOUNDARY_NOT_COVERED;GAP_OR_TOO_FEW_SAMPLES;LOW_SAMPLE_COVERAGE |
| presentation | P019_S001_p3 | P019_S001 | 654.0 | 797.0 | 0.0000 | NO_OVERLAP;BOUNDARY_NOT_COVERED;GAP_OR_TOO_FEW_SAMPLES;LOW_SAMPLE_COVERAGE |
| presentation | P019_S001_p4 | P019_S001 | 930.0 | 1102.0 | 0.0000 | NO_OVERLAP;BOUNDARY_NOT_COVERED;GAP_OR_TOO_FEW_SAMPLES;LOW_SAMPLE_COVERAGE |
| transition | P019_S001_t1 | P019_S001 | 216.0 | 349.0 | 0.0000 | NO_OVERLAP;BOUNDARY_NOT_COVERED;GAP_OR_TOO_FEW_SAMPLES;LOW_SAMPLE_COVERAGE |
| transition | P019_S001_t2 | P019_S001 | 521.0 | 654.0 | 0.0000 | NO_OVERLAP;BOUNDARY_NOT_COVERED;GAP_OR_TOO_FEW_SAMPLES;LOW_SAMPLE_COVERAGE |
| transition | P019_S001_t3 | P019_S001 | 797.0 | 930.0 | 0.0000 | NO_OVERLAP;BOUNDARY_NOT_COVERED;GAP_OR_TOO_FEW_SAMPLES;LOW_SAMPLE_COVERAGE |

## Interpretation boundary

This audit establishes availability, numeric integrity, and interval coverage only. It does not establish final physiological signal quality.

The official distributed EMG HDF5 groups are not trusted because the official code selected columns 0-1; this audit uses descriptor-resolved true EMG channels.
