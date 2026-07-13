# DEJA-VU Cohort B Label-Policy Capacity Audit

Generated: `2026-07-13T15:55:44.492029+00:00`

Scope: the accepted strict paired EEG+EMG cohort only (24 participants, 30 participant-sessions, 90 emotional presentations).

Only post-stimulus (`after`) self-ratings are evaluated. No policy is selected in this audit.

## Policy capacity

| Task | Policy | Retained | Dropped | Low | High | Majority baseline | Participants both classes | Single-class participants | Sessions both classes | Single-class sessions | Videos both classes | Single-class videos | Singleton videos |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| valence | discard_midpoint | 75 | 15 | 53 | 22 | 0.7067 | 14 | 10 | 17 | 13 | 4 | 12 | 4 |
| valence | midpoint_as_low | 90 | 0 | 68 | 22 | 0.7556 | 16 | 8 | 20 | 10 | 5 | 11 | 4 |
| valence | midpoint_as_high | 90 | 0 | 53 | 37 | 0.5889 | 19 | 5 | 22 | 8 | 9 | 7 | 4 |
| arousal | discard_midpoint | 71 | 19 | 33 | 38 | 0.5352 | 9 | 15 | 10 | 20 | 11 | 4 | 4 |
| arousal | midpoint_as_low | 90 | 0 | 52 | 38 | 0.5778 | 14 | 10 | 17 | 13 | 11 | 5 | 4 |
| arousal | midpoint_as_high | 90 | 0 | 33 | 57 | 0.6333 | 14 | 10 | 16 | 14 | 11 | 5 | 4 |

## Definitions

- `discard_midpoint`: score 5 is removed; `<5=low`, `>5=high`.
- `midpoint_as_low`: `<=5=low`, `>5=high`.
- `midpoint_as_high`: `<5=low`, `>=5=high`.
- Majority baseline is descriptive only and is not a model result.

## Constraints for the next stage

- `VIDEO_NAME` remains the held-out content identity.
- Four videos are represented by only one participant; those videos cannot support a strong standalone held-out-content test fold.
- A policy must not be selected merely because it gives a convenient class balance or future model result.
- Final Joint Subject-Stimulus CV construction remains blocked until this report is reviewed.

## Outputs

- `manifests/dejavu_cohort_b_emotional_label_candidates.csv`
- `docs/dejavu_cohort_b_label_policy_summary.csv`
- `docs/dejavu_cohort_b_label_policy_by_participant.csv`
- `docs/dejavu_cohort_b_label_policy_by_session.csv`
- `docs/dejavu_cohort_b_label_policy_by_video.csv`
- `docs/dejavu_cohort_b_label_policy_audit.json`

## Decision

**Final binary valence policy: NOT SELECTED.**  
**Final binary arousal policy: NOT SELECTED.**
