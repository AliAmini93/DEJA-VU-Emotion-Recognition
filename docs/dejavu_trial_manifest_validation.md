# DEJA-VU Trial Manifest — Preliminary Data-Capacity Validation

**This is a descriptive capacity report, not a CV fold design.** No folds are
constructed here. All figures are counted directly from
`manifests/dejavu_stimulus_presentation_manifest.csv` and
`dejavu_transition_manifest.csv` (themselves built from the official
database + verified segment files — see `docs/dejavu_label_rating_policy_audit.md`
and `docs/dejavu_stimulus_definition_audit.md`).

## Headline counts

| Metric | Value |
|---|---|
| Total stimulus presentations | 136 |
| Emotional presentations (baseline excluded) | 102 |
| Baseline presentations | 34 |
| Transition intervals | 102 |
| Independent participants | 28 |
| Participant-sessions | 34 |
| Unique videos (emotional stimuli) | 16 |
| Unique stimulus sources/corpora | 3 (`FilmStim`, `EmoStim`, `EmoStim, FilmStim`) |
| Unique quadrants | 3 (A/Fun, B/Fear, C/Sadness) + baseline D |
| Unique sequence permutations | 6 (all 3! orderings of A/B/C) |

**Segment count is not used as sample size anywhere in this report** — the
unit of account throughout is presentations (136) or transitions (102), and
even these are explicitly flagged elsewhere (`docs/dejavu_trial_unit_preliminary_audit.md`)
as non-independent within a session.

## Participants per video / sessions per video

See `docs/dejavu_stimulus_repetition_support.csv` for the full table. Range:
1 participant (`The Exorcist`, `There is something about Mary 2`,
`The Shining 2`, `Fish called Wanda`) to 12 participants (`The Champ`,
`28 days later`). No two videos have identical repetition counts across the
full range.

## Valence/arousal label availability

**0 missing** valence or arousal values across all 136 presentations
(`docs/dejavu_label_rating_policy_audit.md` — every presentation has exactly
2 ratings, before and after; the manifest's provisional `valence_rating`
column, built by preferring `after` over `before`, has 0 nulls).

## Midpoint prevalence

Using the manifest's provisional (after-preferred) rating column: 27/136
(19.9%) valence ratings equal the scale midpoint (5). See
`docs/dejavu_label_rating_policy_audit.md` for the full before/after
breakdown per dimension — this is **not** a finalized label policy figure,
only a sizing fact.

## Repeated-session nesting

6 of 28 participants have 2 sessions (`P001, P002, P007, P009, P011, P017`);
the remaining 22 have exactly 1. This nesting (2 sessions can share a
participant) must be accounted for in any subject-level split — a
participant's two sessions must never be split across train/test.

## Trials (presentations) per participant

**Min 4, max 8** — participants with 1 session have exactly 4 presentations
(1 baseline + 3 emotional); participants with 2 sessions have 8 (2×4). No
participant has a partial/irregular presentation count.

## Emotional presentations per participant

**Min 3, max 6** — mirrors the above (3 per single session, 6 for the two-
session participants).

## Did every participant see the same videos?

**No.** Confirmed directly: the set of emotional `video_name`s seen is not
identical across all 28 participants (different specific clips are assigned
per the sequence-permutation design, especially for the 6 two-session
participants whose second session used different specific clips than their
first — e.g. `P017` saw `The Shining` in session 1 and `The Shining 2` in
session 2, both quadrant B/Fear). This directly affects any per-video
content-held-out design: it is not a simple "shared stimulus set" like DEAP.

## Does each video belong to only one quadrant?

**Yes, with zero exceptions** — checked across all 16 emotional videos and
102 presentations. This is a fixed, deterministic mapping in this dataset.

## Stimulus-label association strength

Because every video maps to exactly one quadrant (100% deterministic,
verified above), `video_name` and `canonical_quadrant` are **perfectly
confounded** in this dataset as distributed — there is no video that
appears under more than one quadrant/emotion label. This is exactly the
condition `docs/leakage_risk_register.md` risk #8 (stimulus-label
confounding) warns about: a model could learn to key off low-level
video-specific features rather than genuine affective response, and no
within-dataset control (e.g. the same video appearing under two different
quadrant labels) exists to disentangle the two. This is reported as a
structural property of the distributed data, not fixed or worked around
here.

## Outcome

This report is descriptive only. See `docs/dejavu_stimulus_definition_audit.md`
for the content-identity-unit conclusion and
`docs/dejavu_label_rating_policy_audit.md` for the label-policy status —
both remain inputs to a future CV design, not resolved into folds by this
stage.
