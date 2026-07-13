# DEJA-VU Label and Rating Policy Audit

**Question answered: why 272 rating rows for 136 presentations?**
**Answer: exactly 2 ratings per presentation — one `before` and one `after`
— 136 × 2 = 272.** Verified directly, not inferred: `rating_time` has
exactly two values (`before`: 136 rows, `after`: 136 rows), and grouping by
`(subject, session, video_name, rating_time)` yields a maximum group size of
1 (no duplicates anywhere).

## Ratings per participant-session

Exactly **8 ratings per session** for all 34 sessions (std = 0.0): 4
presentations (1 baseline + 3 emotional quadrants) × 2 (before/after) = 8.
No session has more or fewer.

## Ratings per video presentation

**Exactly 2** (one `before`, one `after`) for every one of the 136
presentations — confirmed for baseline too (`quadrant='D'` has 68 rows =
34 sessions × 2, the same 1:1 pattern as the emotional quadrants). No
presentation has 0, 1, or >2 ratings.

## Before vs. after — not duplicates, not interchangeable

Compared `before` and `after` valence directly for every presentation: they
are identical in only **16 of 136** cases (11.8%) — the two ratings capture
genuinely different measurements (pre-exposure anticipatory/current-mood
state vs. post-exposure emotional response), not a duplicated or redundant
column. **This means a label policy must explicitly choose which of the two
to use (or how to combine them) — this is not a cosmetic detail.**

## Duplicated or conflicting ratings

**None found.** Grouping by `(subject, session, video_name, rating_time)`
produces a maximum group size of 1 across all 272 rows — no participant-
session-video-timing combination has more than one rating row.

## Self-report vs. normative

All three rated dimensions (`rating_valence`, `rating_arousal`,
`rating_dominance`) are **self-report** ratings collected from the
participant per-presentation (standard SAM-style 3-dimension self-assessment
scale), not normative/externally-assigned labels. This is stated directly
from the schema (per-subject, per-session rows) and is consistent with the
Zenodo record description's "self-reported based emotion induction success
rates."

## Scale, range, and missing values

- **Range: 1–9 inclusive**, all 9 integer values observed for all three
  dimensions, both `before` and `after`. No values outside 1–9.
- **Missing values: 0** across all 272 rows × 4 non-key columns (`isna().sum()`
  is zero everywhere).
- **Midpoint (value = 5) prevalence:**

  | Dimension | `before` | `after` |
  |---|---|---|
  | Valence | 38/136 (27.9%) | 27/136 (19.9%) |
  | Arousal | 30/136 (22.1%) | 27/136 (19.9%) |
  | Dominance | 30/136 (22.1%) | 29/136 (21.3%) |

  Midpoint values are **not rare** (roughly a fifth to a quarter of ratings)
  — a "discard midpoint" binary-label policy would remove a non-trivial
  fraction of the data, not a negligible edge case.

## Can labels be joined 1:1 to presentation rows without guessing?

**Not to a single label without an explicit policy choice.** Each
presentation has exactly 2 ratings (`before`, `after`), not 1 — a 1:1 join
requires deciding which one (or a combination) constitutes "the" label. This
decision is **not made here**, per instructions ("do not define binary
valence/arousal labels until the actual scale and midpoint policy are
verified... do not choose based on class balance or future model
performance").

## Candidate label policies — presented, not chosen

| Policy | Description | Consequence |
|---|---|---|
| `after_only` | Use only the post-exposure `after` rating as the presentation's label | Discards the `before` measurement entirely; matches "response to stimulus" framing |
| `before_only` | Use only the pre-exposure `before` rating | Measures anticipatory/baseline state, not response to the stimulus — likely the wrong choice for an emotion-*induction* label, but stated as a candidate, not ruled out by this audit |
| `after_minus_before` (delta) | Use the change in rating as the label | Requires deciding how to binarize/bucket a difference score; changes the scale and midpoint definition entirely |
| `discard_midpoint` | Treat value 5 as unusable, drop those rows, binarize the remainder as `>5` / `<5` | Removes ~20–28% of rows depending on dimension/timing — must be sized and reported, not silently applied |
| `midpoint_as_low` | Fold value 5 into the low/negative class | No rows dropped; changes class balance in a specific, reportable direction |
| `midpoint_as_high` | Fold value 5 into the high/positive class | No rows dropped; changes class balance in the other specific, reportable direction |

None of these is selected here. The project's `EmotionRecognitionDEAP-I-DARE`
predecessor's own `working_proposal_v1_1.md` note (see
`docs/environment_audit.md`'s carried-over project context) explicitly flags
this same open question for that project's own label harmonization — this
DEJA-VU dataset needs its own explicit decision, made deliberately, not
inherited.

## Effect of midpoint removal (reported, not applied)

Removing midpoint (`=5`) ratings would leave, depending on dimension/timing,
between 72.1% (`before` valence) and 80.1% (`after` valence/arousal) of the
136 presentations with a usable binary label under a `discard_midpoint`
policy. This is reported as a sizing fact only — no rows are removed by this
audit.

## Manifest note

`manifests/dejavu_stimulus_presentation_manifest.csv` currently populates
`valence_rating`/`arousal_rating`/`dominance_rating` using a **provisional,
clearly-labeled default** (prefer `after` if present, else `before` — see
`rating_policy_status` column, which records the exact before/after row
counts found for every presentation so this default can be audited or
overridden later). This default is **not** the label-policy decision
required by this audit — it exists only so the manifest has a single numeric
column per dimension for downstream tooling to reference; the actual binary-
label policy remains **NOT DEFINED**, per instructions.

## Outcome

**Rating join: MULTIPLE-PER-PRESENTATION** (2 per presentation: before/after
— not 1:1, and not resolved to 1:1 by this audit). **Binary valence label
policy: NOT DEFINED. Binary arousal label policy: NOT DEFINED.** Both require
an explicit, separately-justified decision before any fold or label
construction.
