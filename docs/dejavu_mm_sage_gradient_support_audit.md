# DEJA-VU MM-SAGE-DG Gradient-Support Capacity Audit

Generated: `2026-07-15T10:24:28.442717+00:00`

This is a data-capacity audit only. No EEG/EMG model and no MM-SAGE gradient was trained.

## Frozen inputs

- Label manifest: `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition/manifests/dejavu_cohort_b_primary_labels.csv`
- Label-manifest SHA-256: `0fb0d40696d1f700d7f517e3296b58c4e180ea9834f326fd16e9700c1cfa9890`
- Frozen assignments: `/mnt/HDD/AliWorks/DEJA-VU-Emotion-Recognition/folds/dejavu_joint_cv_repeated_assignments.csv`
- Git branch: `dejavu-cohort-b-joint-cv-audit`
- Git HEAD: `719d300715007a22e9b86354740d3d46a1b28e9c`
- Cohort B: 24 participants, 30 participant-sessions, 90 emotional presentations, 16 exact videos.
- Primary labels: after-only discard midpoint.
- Frozen evaluation: 5 repetitions × 3 subject folds × 3 exact-video folds.

## Eligibility definitions

- `weak_1trial`: at least one scored trial for the subject-class.
- `minimal_2trials`: at least two scored trials for the subject-class.
- `strong_2trials_2videos`: at least two scored trials from at least two exact videos for the subject-class.
- MM-SAGE consensus threshold audited here: at least three eligible subjects per class.

## Scenario definitions

- `outer_source`: final outer-cell source pool, normally 16 subjects and 10/11 exact videos.
- `inner_subject_only`: one of the two source subject folds is reserved for validation.
- `inner_video_only`: one of the two source video folds is reserved for validation.
- `inner_joint`: one source subject fold and one source video fold remain for fitting; the other source folds form a leakage-safe joint validation configuration.

## Aggregate gradient-support capacity

| Scenario | Task | Class | Eligibility | Configs | Eligible M min/median/max | M≥3 rate | M<3 configs | Class trials min/median | Min exact videos |
|---|---|---|---|---|---|---|---|---|---|
| inner_joint | arousal | high | minimal_2trials | 180 | 0/1.0/5 | 0.133 | 156 | 0/4.0 | 0 |
| inner_joint | arousal | high | strong_2trials_2videos | 180 | 0/1.0/5 | 0.133 | 156 | 0/4.0 | 0 |
| inner_joint | arousal | high | weak_1trial | 180 | 0/3.0/6 | 0.600 | 72 | 0/4.0 | 0 |
| inner_joint | arousal | low | minimal_2trials | 180 | 0/1.0/3 | 0.022 | 176 | 0/4.0 | 0 |
| inner_joint | arousal | low | strong_2trials_2videos | 180 | 0/1.0/3 | 0.022 | 176 | 0/4.0 | 0 |
| inner_joint | arousal | low | weak_1trial | 180 | 0/3.0/6 | 0.600 | 72 | 0/4.0 | 0 |
| inner_joint | valence | high | minimal_2trials | 180 | 0/0.0/1 | 0.000 | 180 | 0/2.0 | 0 |
| inner_joint | valence | high | strong_2trials_2videos | 180 | 0/0.0/1 | 0.000 | 180 | 0/2.0 | 0 |
| inner_joint | valence | high | weak_1trial | 180 | 0/2.0/5 | 0.444 | 100 | 0/2.0 | 0 |
| inner_joint | valence | low | minimal_2trials | 180 | 0/1.0/5 | 0.156 | 152 | 1/5.0 | 1 |
| inner_joint | valence | low | strong_2trials_2videos | 180 | 0/1.0/5 | 0.156 | 152 | 1/5.0 | 1 |
| inner_joint | valence | low | weak_1trial | 180 | 1/4.0/8 | 0.867 | 24 | 1/5.0 | 1 |
| inner_subject_only | arousal | high | minimal_2trials | 90 | 0/3.0/5 | 0.556 | 40 | 2/8.0 | 2 |
| inner_subject_only | arousal | high | strong_2trials_2videos | 90 | 0/3.0/5 | 0.556 | 40 | 2/8.0 | 2 |
| inner_subject_only | arousal | high | weak_1trial | 90 | 2/5.0/8 | 0.933 | 6 | 2/8.0 | 2 |
| inner_subject_only | arousal | low | minimal_2trials | 90 | 0/2.0/5 | 0.200 | 72 | 3/7.0 | 2 |
| inner_subject_only | arousal | low | strong_2trials_2videos | 90 | 0/2.0/5 | 0.200 | 72 | 3/7.0 | 2 |
| inner_subject_only | arousal | low | weak_1trial | 90 | 2/4.0/7 | 0.956 | 4 | 3/7.0 | 2 |
| inner_subject_only | valence | high | minimal_2trials | 90 | 0/1.0/2 | 0.000 | 90 | 1/5.0 | 1 |
| inner_subject_only | valence | high | strong_2trials_2videos | 90 | 0/1.0/2 | 0.000 | 90 | 1/5.0 | 1 |
| inner_subject_only | valence | high | weak_1trial | 90 | 1/4.0/6 | 0.844 | 14 | 1/5.0 | 1 |
| inner_subject_only | valence | low | minimal_2trials | 90 | 0/4.0/7 | 0.711 | 26 | 4/11.0 | 3 |
| inner_subject_only | valence | low | strong_2trials_2videos | 90 | 0/4.0/7 | 0.711 | 26 | 4/11.0 | 3 |
| inner_subject_only | valence | low | weak_1trial | 90 | 3/7.0/8 | 1.000 | 0 | 4/11.0 | 3 |
| inner_video_only | arousal | high | minimal_2trials | 90 | 0/1.0/8 | 0.356 | 58 | 2/7.0 | 1 |
| inner_video_only | arousal | high | strong_2trials_2videos | 90 | 0/1.0/8 | 0.356 | 58 | 2/7.0 | 1 |
| inner_video_only | arousal | high | weak_1trial | 90 | 2/6.0/10 | 0.867 | 12 | 2/7.0 | 1 |
| inner_video_only | arousal | low | minimal_2trials | 90 | 0/1.0/3 | 0.067 | 84 | 1/7.0 | 1 |
| inner_video_only | arousal | low | strong_2trials_2videos | 90 | 0/1.0/3 | 0.067 | 84 | 1/7.0 | 1 |
| inner_video_only | arousal | low | weak_1trial | 90 | 1/6.0/10 | 0.933 | 6 | 1/7.0 | 1 |
| inner_video_only | valence | high | minimal_2trials | 90 | 0/0.0/2 | 0.000 | 90 | 0/5.0 | 0 |
| inner_video_only | valence | high | strong_2trials_2videos | 90 | 0/0.0/2 | 0.000 | 90 | 0/5.0 | 0 |
| inner_video_only | valence | high | weak_1trial | 90 | 0/4.0/9 | 0.778 | 20 | 0/5.0 | 0 |
| inner_video_only | valence | low | minimal_2trials | 90 | 0/2.0/7 | 0.489 | 46 | 3/11.0 | 1 |
| inner_video_only | valence | low | strong_2trials_2videos | 90 | 0/2.0/7 | 0.489 | 46 | 3/11.0 | 1 |
| inner_video_only | valence | low | weak_1trial | 90 | 3/9.0/14 | 1.000 | 0 | 3/11.0 | 1 |
| outer_source | arousal | high | minimal_2trials | 45 | 1/5.0/10 | 0.867 | 6 | 7/17.0 | 3 |
| outer_source | arousal | high | strong_2trials_2videos | 45 | 1/5.0/10 | 0.867 | 6 | 7/17.0 | 3 |
| outer_source | arousal | high | weak_1trial | 45 | 5/10.0/13 | 1.000 | 0 | 7/17.0 | 3 |
| outer_source | arousal | low | minimal_2trials | 45 | 0/3.0/6 | 0.867 | 6 | 8/15.0 | 4 |
| outer_source | arousal | low | strong_2trials_2videos | 45 | 0/3.0/6 | 0.867 | 6 | 8/15.0 | 4 |
| outer_source | arousal | low | weak_1trial | 45 | 5/9.0/13 | 1.000 | 0 | 8/15.0 | 4 |
| outer_source | valence | high | minimal_2trials | 45 | 0/1.0/3 | 0.133 | 39 | 4/10.0 | 3 |
| outer_source | valence | high | strong_2trials_2videos | 45 | 0/1.0/3 | 0.133 | 39 | 4/10.0 | 3 |
| outer_source | valence | high | weak_1trial | 45 | 4/8.0/12 | 1.000 | 0 | 4/10.0 | 3 |
| outer_source | valence | low | minimal_2trials | 45 | 2/7.0/12 | 0.978 | 1 | 14/23.0 | 4 |
| outer_source | valence | low | strong_2trials_2videos | 45 | 2/7.0/12 | 0.978 | 1 | 14/23.0 | 4 |
| outer_source | valence | low | weak_1trial | 45 | 10/13.0/16 | 1.000 | 0 | 14/23.0 | 4 |

## Same-subject support for both classes

This is diagnostic. The class-conditional consensus can use different subject sets, but a very small intersection means that Low and High gradients are estimated from materially different subject populations.

| Scenario | Task | Eligibility | Configs | Both-class subjects min/median/max | Same-subject trio rate |
|---|---|---|---|---|---|
| inner_joint | arousal | minimal_2trials | 180 | 0/0.0/1 | 0.000 |
| inner_joint | arousal | strong_2trials_2videos | 180 | 0/0.0/1 | 0.000 |
| inner_joint | arousal | weak_1trial | 180 | 0/0.0/3 | 0.044 |
| inner_joint | valence | minimal_2trials | 180 | 0/0.0/1 | 0.000 |
| inner_joint | valence | strong_2trials_2videos | 180 | 0/0.0/1 | 0.000 |
| inner_joint | valence | weak_1trial | 180 | 0/1.0/5 | 0.178 |
| inner_subject_only | arousal | minimal_2trials | 90 | 0/0.0/1 | 0.000 |
| inner_subject_only | arousal | strong_2trials_2videos | 90 | 0/0.0/1 | 0.000 |
| inner_subject_only | arousal | weak_1trial | 90 | 0/2.0/5 | 0.222 |
| inner_subject_only | valence | minimal_2trials | 90 | 0/0.0/2 | 0.000 |
| inner_subject_only | valence | strong_2trials_2videos | 90 | 0/0.0/2 | 0.000 |
| inner_subject_only | valence | weak_1trial | 90 | 0/3.0/6 | 0.578 |
| inner_video_only | arousal | minimal_2trials | 90 | 0/0.0/1 | 0.000 |
| inner_video_only | arousal | strong_2trials_2videos | 90 | 0/0.0/1 | 0.000 |
| inner_video_only | arousal | weak_1trial | 90 | 0/1.0/4 | 0.222 |
| inner_video_only | valence | minimal_2trials | 90 | 0/0.0/1 | 0.000 |
| inner_video_only | valence | strong_2trials_2videos | 90 | 0/0.0/1 | 0.000 |
| inner_video_only | valence | weak_1trial | 90 | 0/2.0/8 | 0.378 |
| outer_source | arousal | minimal_2trials | 45 | 0/0.0/1 | 0.000 |
| outer_source | arousal | strong_2trials_2videos | 45 | 0/0.0/1 | 0.000 |
| outer_source | arousal | weak_1trial | 45 | 0/3.0/8 | 0.756 |
| outer_source | valence | minimal_2trials | 45 | 0/1.0/2 | 0.000 |
| outer_source | valence | strong_2trials_2videos | 45 | 0/1.0/2 | 0.000 |
| outer_source | valence | weak_1trial | 45 | 1/6.0/11 | 0.956 |

## Predeclared empirical gates

### Valence

| Eligibility | Outer min M | Outer M≥3 rate | All outer cells pass | Inner-joint M≥3 rate | Outer min same-subject both classes | Same-subject trio rate |
|---|---|---|---|---|---|---|
| weak_1trial | 4 | 1.000 | True | 0.656 | 1 | 0.956 |
| minimal_2trials | 0 | 0.556 | False | 0.078 | 0 | 0.000 |
| strong_2trials_2videos | 0 | 0.556 | False | 0.078 | 0 | 0.000 |

Empirical capacity status: **WEAK_SINGLE_TRIAL_SUPPORT_ONLY**

### Arousal

| Eligibility | Outer min M | Outer M≥3 rate | All outer cells pass | Inner-joint M≥3 rate | Outer min same-subject both classes | Same-subject trio rate |
|---|---|---|---|---|---|---|
| weak_1trial | 5 | 1.000 | True | 0.600 | 0 | 0.756 |
| minimal_2trials | 0 | 0.867 | False | 0.078 | 0 | 0.000 |
| strong_2trials_2videos | 0 | 0.867 | False | 0.078 | 0 | 0.000 |

Empirical capacity status: **WEAK_SINGLE_TRIAL_SUPPORT_ONLY**

## Overall empirical status

**LIMITED_OR_WEAK_MECHANISM_SUPPORT**

This status is not yet the paper-level verdict. It is the exact data-support result required before deciding whether the full MM-SAGE-DG mechanism, a weakened single-trial variant, or only a secondary stress test is defensible.

## Important interpretation rules

1. Windows from one presentation do not create independent trials or exact-video diversity.
2. `uniform_random_trio_acceptance_probability` assumes subjects are sampled uniformly from the nominal source pool. A sampler restricted to eligible subjects avoids resampling, but cannot create missing subject-class evidence.
3. Different eligible subject sets for Low and High can confound class comparison with subject composition.
4. `inner_joint` is deliberately strict because leakage-safe hyperparameter selection must reserve both source subjects and source videos.
5. Passing this support audit does not prove that real gradients are stable or emotion-specific. A later pilot must still compare real-class, shuffled-class, and stimulus-controlled gradient agreement.

## Most capacity-limited outer configurations

| Outer cell | Task | Class | Strong eligible M | Scored class trials | Exact videos | Eligible subjects |
|---|---|---|---|---|---|---|
| R00_S1_V1 | valence | high | 0 | 4 | 3 | — |
| R02_S1_V1 | valence | high | 0 | 5 | 3 | — |
| R04_S3_V2 | valence | high | 0 | 6 | 3 | — |
| R01_S3_V2 | valence | high | 0 | 7 | 3 | — |
| R02_S1_V1 | arousal | low | 0 | 8 | 4 | — |
| R00_S2_V1 | valence | high | 1 | 6 | 3 | P002 |
| R02_S3_V1 | valence | high | 1 | 6 | 3 | P001 |
| R03_S1_V2 | valence | high | 1 | 6 | 3 | P007 |
| R00_S3_V1 | valence | high | 1 | 6 | 4 | P002 |
| R03_S3_V1 | valence | high | 1 | 6 | 4 | P002 |
| R04_S2_V2 | valence | high | 1 | 6 | 4 | P002 |
| R00_S1_V1 | arousal | high | 1 | 7 | 3 | P010 |
| R03_S1_V1 | valence | high | 1 | 7 | 3 | P001 |
| R02_S2_V1 | valence | high | 1 | 7 | 4 | P001 |
| R02_S3_V1 | arousal | high | 1 | 7 | 4 | P011 |
| R01_S1_V2 | valence | high | 1 | 7 | 5 | P002 |
| R03_S1_V2 | arousal | high | 1 | 7 | 5 | P011 |
| R04_S2_V3 | valence | high | 1 | 8 | 4 | P002 |
| R01_S2_V2 | valence | high | 1 | 8 | 5 | P002 |
| R00_S2_V3 | arousal | low | 1 | 8 | 6 | P021 |

## Outputs

- `docs/dejavu_mm_sage_gradient_support_by_subject.csv`
- `docs/dejavu_mm_sage_gradient_support_capacity.csv`
- `docs/dejavu_mm_sage_gradient_support_class_pair.csv`
- `docs/dejavu_mm_sage_gradient_support_video_support.csv`
- `docs/dejavu_mm_sage_gradient_support_aggregate.csv`
- `docs/dejavu_mm_sage_gradient_support_pair_aggregate.csv`
- `docs/dejavu_mm_sage_gradient_support_audit.json`
- `docs/dejavu_mm_sage_gradient_support_audit.md`
