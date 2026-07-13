# DEJA-VU Cohort B — Paired EEG+EMG Strict

Generated: `2026-07-13T15:52:44.668943+00:00`

## Cohort rule

A participant-session is retained only when all four stimulus-presentation intervals and all three transition intervals pass strict two-channel raw-EMG QC. The EEG and EMG rows are then retained or excluded together at the whole-session level.

No raw file was deleted or modified. Exclusion is manifest-based.

## Final capacity

| Metric | Value |
|---|---:|
| Independent participants | 24 |
| Participant-sessions | 30 |
| Participants with two retained sessions | 6 |
| All presentations | 120 |
| Emotional presentations | 90 |
| Baseline presentations | 30 |
| Transition intervals | 90 |
| Unique emotional videos | 16 |

## Excluded participant-sessions

| Participant-session | Reason |
|---|---|
| P012_S001 | PRESENTATION_STRICT_FAIL_4;TRANSITION_STRICT_FAIL_3 |
| P015_S001 | PRESENTATION_STRICT_FAIL_4;TRANSITION_STRICT_FAIL_3 |
| P019_S001 | PRESENTATION_STRICT_FAIL_4;TRANSITION_STRICT_FAIL_3 |
| P020_S001 | PRESENTATION_STRICT_FAIL_4;TRANSITION_STRICT_FAIL_3 |

## Video-support impact

- Emotional videos before strict exclusion: `16`
- Emotional videos after strict exclusion: `16`
- Videos lost entirely: `None`
- Videos represented by only one participant: `Fish called Wanda, The Exorcist, The Shining 2, There is something about Mary 2`
- Videos with at least two participants: `12`
- Participant support per retained video: min `1`, median `5.5`, max `11`

## Acceptance checks

| Check | Result |
|---|---|
| `excluded_sessions_match_expected` | PASS |
| `participants_equal_24` | PASS |
| `sessions_equal_30` | PASS |
| `presentations_equal_120` | PASS |
| `emotional_presentations_equal_90` | PASS |
| `baseline_presentations_equal_30` | PASS |
| `transitions_equal_90` | PASS |
| `all_retained_presentations_strict` | PASS |
| `all_retained_transitions_strict` | PASS |
| `no_excluded_session_in_presentation_manifest` | PASS |
| `no_excluded_session_in_transition_manifest` | PASS |

## Decision

**Cohort B accepted and ready for label-policy capacity audit.**

## Outputs

- `manifests/dejavu_cohort_b_sessions.csv`
- `manifests/dejavu_cohort_b_presentations.csv`
- `manifests/dejavu_cohort_b_emotional_presentations.csv`
- `manifests/dejavu_cohort_b_transitions.csv`
- `docs/dejavu_cohort_b_video_support.csv`
- `docs/dejavu_cohort_b_definition.json`
