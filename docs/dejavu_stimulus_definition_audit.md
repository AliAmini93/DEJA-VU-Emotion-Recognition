# DEJA-VU Stimulus Identity Audit

Evaluates 8 candidate definitions of "stimulus identity" for a future
content-held-out evaluation design. Full matrix:
`docs/dejavu_stimulus_definition_matrix.csv`. All figures computed from
`manifests/dejavu_stimulus_presentation_manifest.csv` /
`dejavu_transition_manifest.csv` and the official database — not assumed.

## Key facts established

- **Quadrant and emotion are the label, not content**: `canonical_quadrant`
  (A/B/C) maps 1:1 to `emotion_name` (Fun/Fear/Sadness respectively) for
  every one of the 136 emotional presentations, with zero exceptions. All 28
  participants are exposed to all 3 quadrants (and baseline) — using
  quadrant or emotion as a "held-out content" unit would silently hold out
  an entire label class, not a content item. **Per instructions, quadrant is
  not treated as content identity.**
- **`video_name` genuinely identifies distinct content**, but with **severe,
  real repetition skew**: 16 unique emotional videos across 136
  presentations, ranging from 1 participant (`The Exorcist`, `There is
  something about Mary 2`, `The Shining 2`, `Fish called Wanda`) to 12
  participants (`The Champ`, `28 days later`). Baseline is always the single
  video `Clouds` (34/34 sessions, zero content variation — baseline cannot
  support content-held-out evaluation at all, by construction).
- **`source`** (`FilmStim` / `EmoStim` / `EmoStim, FilmStim`) is a
  **stimulus-corpus/collection-method tag, not movie identity** — it spans
  multiple quadrants and multiple distinct videos each. It must not be
  conflated with "which movie" — confirmed directly: e.g. `The Shining` and
  `The Shining 2` (same on-screen franchise, likely different clips) have
  *different* `source` values (`EmoStim` vs. `FilmStim`) despite both being
  quadrant B / Fear.
- **A normalized video ID** (stripping a trailing " 2"/digit) merges exactly
  2 near-duplicate pairs (`The Shining`/`The Shining 2`,
  `There is something about Mary`/`...2`), reducing 16 → 14 units. This
  merge is **not verified to be content-equivalent** — it assumes "X" and
  "X 2" are interchangeable stimuli, which nothing in the database confirms
  or denies (no shared identifier links them beyond the name pattern).
- **Sequence permutation**: exactly 6 distinct values found
  (`ABC,ACB,BAC,BCA,CAB,CBA` — all 3! permutations of the 3 quadrants),
  1–8 sessions each — confirms the Zenodo description's "six possible
  emotional sequences" directly from data, not assumed.
- **Transition type**: 9 distinct values (`D_to_A/B/C` plus all 6 ordered
  pairs among A/B/C), 6–15 occurrences each — a session-order artifact, not
  a content-identity dimension.
- **Chronological position** (1–4): purely ordinal, identical structure
  every session, carries no content information by itself.

## Candidate unit evaluation (see CSV for full numeric detail)

| Candidate | Usable for content-held-out? | Why |
|---|---|---|
| `exact video_name` | **PARTIAL** | Correct semantic granularity; 4/16 videos have only 1 participant — too sparse for balanced folds without further handling |
| `normalized_video_id` | PARTIAL | Same issue, marginally fewer units; equivalence assumption unverified |
| `source` (stimulus corpus) | **NO** | Only 3 coarse values; describes corpus/method, not content |
| `canonical_quadrant` | **NO** (rejected) | Is the label itself |
| `emotion_name` | **NO** (rejected) | Redundant with quadrant, also the label |
| `transition_type` | N/A | Different research question (order/transition generalization) |
| `sequence_permutation` | N/A | Different research question (sequence generalization) |
| `chronological_position` | **NO** (rejected) | Purely ordinal, no content information |

## Canonical held-out content unit:

**VIDEO_NAME**

Justification: it is the only candidate that actually identifies specific
stimulus content rather than a label, a corpus tag, or an ordering artifact.
It is **not** selected because it produces convenient folds — on the
contrary, its repetition distribution (1–12 participants per video) makes
balanced content-held-out folds **difficult**, and this difficulty is
reported explicitly rather than papered over by switching to a more
"convenient" but semantically wrong unit (e.g. quadrant). Any future
content-held-out CV design using `video_name` must explicitly handle or
report on the 4 single-participant videos (they cannot serve as both train
and held-out content simultaneously, and cannot themselves be a held-out
fold with meaningful test support).

`normalized_video_id` is recorded as a documented alternative, not
selected as canonical, because its content-equivalence assumption for the
two merged pairs is unverified.
