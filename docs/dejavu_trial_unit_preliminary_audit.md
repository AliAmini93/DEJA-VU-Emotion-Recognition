# DEJA-VU Preliminary Trial-Unit Audit

**This is a preliminary audit, not a final trial manifest.** No immutable
trial manifest is produced here — per instructions, that is deferred until
every open item below is resolved with certainty rather than inference.
Evidence is drawn from `docs/dejavu_official_code_audit.md` (code logic) and
`docs/data_audit_dejavu.md` (real extracted file/database inspection).

## What is one raw XDF file?

**One participant-session's complete, continuous, multimodal recording** —
not a trial, not a single stimulus. Confirmed: 34 raw XDF files total, one
per (subject, session) pair, each ~1220 s long, containing all 4 streams
(EEG, ECG, EMG, GSR) for the entire session — baseline, all 3 emotional
quadrants, all 3 transitions, and (per the database's `videos` table) the 8
SAM rating screens and 3 Baraka reset clips too, all in one uninterrupted
LSL recording.

## What is one HDF5 file (`preprocessed/`)?

**The same scope as the raw XDF** — one participant-session's continuous
recording, after filtering/ICA, still spanning the entire ~1220 s session in
one file (verified: `clean_P017_S002.h5`'s EEG dataset is `[N, 7]` for the
whole session, not split per-stimulus). One preprocessed file ≠ one trial;
it is the filtered version of one raw file.

## What is one segment file (`segments/**/*.h5`)?

**One of exactly 7 pre-defined slices of a session**, extracted from the
continuous preprocessed recording by `lib_segment_builder.py`:
1 `neutral_baseline` + 3 `quadrant_*` (one per emotional video) + 3
`transition_*_period` (the interval between consecutive quadrant/baseline
presentations). Confirmed via real file inspection: each segment HDF5 has
its own `start_time`/`end_time`/`duration` and per-modality data sliced to
that window (e.g. `sub-P017/S002_quadrant_A_pos3.h5`: 748.0 s–928.0 s,
180 s duration).

## Does one segment equal one stimulus presentation?

**Only for `neutral_baseline` and `quadrant_*` segments (4 of the 7 per
session).** Each of those corresponds 1:1 to one video-stimulus
presentation (`video_name` stored directly in `segment_info`). The 3
`transition_*_period` segments are **not** stimulus presentations — they are
the inter-stimulus interval *between* two stimulus presentations (during
which a Baraka reset clip plays, per the record description's "69-second
neutral reset periods," though see the open discrepancy below on the exact
duration figure).

## Are transition intervals separate files or annotations?

**Separate files.** Each transition is its own `*_transition_{type}_period.h5`
file with its own `segment_info.transition_type` (e.g. `B_to_A`) — not an
annotation/marker embedded within a continuous quadrant file.

## Are there multiple recordings per participant-session?

**No — exactly one raw XDF file per (subject, session) pair, confirmed for
all 34.** The code's `find_largest_xdf()` (picks the largest-by-bytes `.xdf`
in a folder) exists to handle *possible* halted-session duplicates, per its
own comment, but the distributed archive contains no folder with more than
one `.xdf` file — that disambiguation code path is never actually exercised
by the shipped data.

## What identifies a unique trial?

**Ambiguous — this is the central open question, stated explicitly rather
than guessed.** Two candidate definitions, both directly supported by real
data:

- **Stimulus-presentation trial** (`journey` table row): `(subject, session,
  position)` — 34 sessions × 4 positions = **136**, exactly matching the
  database's `journey` table row count. This is the authors' own apparent
  first-class unit: one emotion-eliciting (or baseline) video presentation.
- **Segment-file trial** (any of the 7 per-session HDF5 outputs):
  `(subject, session, segment_type)` — 34 × 7 = **238**. This includes the
  102 transition segments, which are *derived* (computed from consecutive
  `journey` rows via `identify_transitions()`), not stored as first-class DB
  rows themselves.

No single number is asserted as "the" trial count here. Given the project's
non-negotiable rule #5 (never use segment count as statistical sample
size), **neither 136 nor 238 should be treated as an i.i.d. sample size** —
the true unit of statistical independence is at most the 34 participant-
sessions (arguably just the 28 participants, given within-subject
correlation across a participant's two sessions).

## What identifies a unique stimulus?

**`video_name`**, directly available in `videos`, `journey`, `ratings`, and
`video_mappings`. `video_mappings` additionally provides `emotion`,
`quadrant`, `source`, and `length_sec` per named video (19 distinct videos
catalogued).

## Is video identity available, or only quadrant?

**Both are available**, and they are not the same granularity. `quadrant`
(D/A/B/C) is a coarser 4-way grouping; `video_name` identifies the specific
clip. A leakage-risk mitigation design (risk #8, stimulus-label confounding)
must consciously choose which granularity to condition on — the finer
`video_name` field is present and must not be ignored just because
`quadrant` is more convenient.

## Is chronological ordering explicitly stored?

**Yes, redundantly.** `videos.video_order` (ordinal), `journey.position`
(ordinal within the 4-video journey), and `videos.time_rel` /
`video_start_24` (relative-seconds and absolute clock time) are all stored
explicitly. Chronological order is a first-class stored field, not something
downstream code must infer.

## Can trial onset and offset be reconstructed without guessing?

**Yes, for every stimulus except the last one in a session's timeline** —
with that one exception stated honestly rather than glossed over.
`get_video_timeline()` computes `end_time` for a video as the `start_time`
of the *next* video (`LEAD(v.time_rel) OVER (ORDER BY v.video_order)`), which
is exact for every position except the final one in the session, where there
is no "next" row. For that last video, the code explicitly falls back to
`start_time + expected_duration` (from `video_mappings.length_sec`) and logs
a warning (`"'end_time' ... Not found, using calculated duration"`) — this
one edge case is a **computed approximation**, not a stored ground-truth
value. Confirmed directly in real segment files: all inspected segments
carry explicit `start_time`/`end_time`/`duration` attrs (no `NaN`/missing
values observed in the 233 trusted files checked), so in practice the
approximation appears to already be resolved by the time segments are built
— but the underlying computation path for the last video of a session is a
fallback, not a stored fact, and should be treated as such in any future
onset/offset-sensitive analysis.

## Are 238 segments independent trials or derived windows?

**Neither, simply.** 238 = 136 stimulus-presentation segments (baseline +
quadrants, matching `journey`'s row count) + 102 transition segments
(derived, computed from consecutive `journey` positions, not first-class DB
rows). None of the 238 are statistically independent of one another within
a session — they share the same participant, the same recording apparatus
placement, and adjacent/overlapping physiological state. Non-negotiable
rule #5 forbids treating segment count as sample size regardless of which
of these two numbers (136 or 238) is used.

## Why does the archive contain the observed number of segment entries?

**Fully resolved, not assumed:** 34 sessions × 7 segments/session = 238.
Verified three independent ways: (1) the official code's own
`07_run_segmentation.py` computes `expected_files = len(successful) * 7` and
states "Orchestrates Level 1 segmentation for all 34 sessions"; (2) the
actual archive listing contains exactly 238 files under `segments/`; (3) the
database's `journey` table (136 rows = 34×4) plus 34×3 = 102 derivable
transitions sums to 238. All three agree.

## Open items — explicitly unresolved (per instructions, not guessed)

1. **136 vs. 238 as "the" trial count** — no single answer is asserted; both
   candidate definitions and their provenance are documented above. A final
   choice requires a modeling-design decision, not a data-audit fact.
2. **69 s (record description) vs. 123–143 s / ~133 s (code's transition
   validation window) vs. an observed ~133.0 s in every inspected real
   transition segment** — three different numbers describing
   transition/reset timing appear across the paper description, the
   validation code, and the real data. Not reconciled here.
3. **Channel-order discrepancy** (ECG/GSR raw channel indices, see
   `docs/dejavu_identity_conflict_audit.md`'s incidental finding and
   `docs/leakage_risk_register.md` risk #9 sub-finding B) — affects whether
   "ECG"/"GSR" labeled data in `preprocessed/`/`segments/` files actually
   contains what its channel labels claim. Unresolved.
4. **39 truncated HDF5 files** (11 preprocessed, 28 segments) have not been
   content-inspected at all — their internal `segment_info`/channel
   structure is assumed-but-not-verified to match the pattern found in the
   269 trusted files, pending a possible `unrar` re-extraction.
