# DEJA-VU Data and Evaluation Protocol Status

## Accepted multimodal cohort

The primary EEG+EMG experiments use **Cohort B — Paired EEG+EMG Strict**.

- 24 independent participants
- 30 participant-sessions
- 120 total stimulus presentations
- 90 emotional presentations
- 30 baseline presentations
- 90 transition intervals
- 16 exact emotional `VIDEO_NAME` identities

The following participant-sessions are excluded from the paired cohort because
their true raw-EMG channels fail the strict two-channel signal-quality gate:

- `P012_S001`
- `P015_S001`
- `P019_S001`
- `P020_S001`

Exclusion is manifest-based. No source data file is deleted or renamed.

## EMG source rule

The distributed preprocessed EMG groups must not be used. The official
preprocessing selected battery/status columns rather than the two true EMG
channels. EMG must be reconstructed from the raw XDF stream using descriptor
channel labels and the accepted raw-signal QC rules.

## Primary labels

Only post-stimulus (`after`) self-ratings are used.

Primary binary policy for both targets:

- score `< 5`: low
- score `= 5`: unavailable for that target
- score `> 5`: high

Retained primary-label support:

- Valence: 75 presentations, 53 low and 22 high
- Arousal: 71 presentations, 33 low and 38 high

Score-5 rows remain in the presentation manifest. Multitask training must use
task-specific loss masks.

## Frozen Joint Subject–Stimulus CV

Status: **LOCK_WITH_CAPACITY_CAUTION**

- Exact `VIDEO_NAME` is the held-out content identity.
- 3 subject folds × 3 video folds
- 9 Cartesian joint-test cells per repetition
- 5 deterministic, manifest-hash-derived repetitions
- repetition 0: primary benchmark
- repetitions 1–4: sensitivity only
- no label, EEG, EMG, prediction, or trained metric is used to construct folds
- no repetition is rerolled, removed, or replaced
- all sessions of one participant remain in the same subject fold
- train excludes every held-out participant and every held-out video
- joint test is the intersection of held-out participants and held-out videos
- subject leakage: zero
- video leakage: zero

Because the participant-video graph is sparse, one fixed sensitivity repetition
contains a one-presentation cell and eight task-specific cells across all five
repetitions contain only one class. These cells are retained.

## Metric rule

Headline metrics are computed once per target and repetition after concatenating
predictions from all nine joint-test cells.

- repetition 0 is the primary result
- repetitions 1–4 are sensitivity analyses
- sensitivity repetitions cannot be used for model or hyperparameter selection
- one-class cells must not be scored as standalone Balanced Accuracy,
  Macro-F1, or ROC-AUC units
- undefined cell metrics must not be silently dropped and averaged
- uncertainty must account for participant/video dependence

## Statistical unit

One emotional stimulus presentation is the statistical unit. Windows or
segments derived from a presentation are not independent statistical samples.

## Training status

No physiological model has been trained under this frozen protocol. The next
scientific stage is a leakage-safe shortcut, chance, and null audit on the
frozen repetitions, followed by reproducible raw-EMG reconstruction and
preprocessing.


## Frozen shortcut and null audit

- Unique three-video emotional sequences: 28 across 30 participant-sessions
- NMI(video, emotional presentation position): 0.1103
- No position-based null test remained significant after FDR correction
- Best empirical legal baseline BA: valence 0.5000; arousal 0.3194
- Mandatory primary BA gate: 0.5000 for both tasks

The mandatory gate is `max(0.5, best empirical legal-baseline BA)`. Diagnostic identity priors remain secondary and are not legal priors in the primary unseen-subject plus unseen-video test.
