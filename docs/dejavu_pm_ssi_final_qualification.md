# Final DEJA-VU Qualification Audit for PM-SSI-DG

Generated: `2026-07-15T10:49:51.761989+00:00`

No physiological model was trained. The audit uses the frozen Cohort B manifest, frozen repeated 3×3 Joint Subject–Exact-Video assignments, Raw XDF, and the previously frozen shortcut/null audit.

Verified Raw-XDF EEG mapping: `F3->FP1, S2->FP2, S3->C3, S4->C4, S5->LE, S6->EOG1, S7->EOG2`; `TRG` is excluded. Fz is not present in the distributed raw descriptor or official map.

## Final verdict

**YELLOW — SECONDARY_EXTERNAL_VR_STRESS_TEST_ONLY**

## Headline capacity

| Metric | Value |
|---|---|
| Retained paired trials | 90 |
| Minimum valid paired 5 s windows per trial | 20 |
| Primary minimum legal donors | 2 |
| Primary maximum zero-donor rate | 0.0000 |
| Primary maximum rate with <5 donors | 0.3000 |
| Primary minimum unique donor subjects | 2 |
| Primary minimum unique donor exact videos | 1 |
| Primary inner-joint operational rate | 0.3889 |
| All-repetition inner-joint operational rate | 0.3806 |
| Primary task-specific single-class cells | 2 |
| Primary minimum scored test trials | 3 |
| Shortcut/null decision | PROCEED_WITH_STANDARD_SHORTCUT_GATE |

## Primary repetition donor support

| Task | Min scored source trials | Min Low/High | Min donors | Worst-cell donor P10 | Worst-cell donor median | Max zero rate | Max <5 rate | Min donor subjects | Min donor videos | Min donor quadrants |
|---|---|---|---|---|---|---|---|---|---|---|
| arousal | 21 | 8/7 | 3 | 3.0 | 7.0 | 0.0000 | 0.2381 | 2 | 1 | 1 |
| valence | 20 | 14/4 | 2 | 3.0 | 10.0 | 0.0000 | 0.3000 | 2 | 1 | 1 |

## Primary outer-test support

| Outer cell | Task | Raw test | Scored | Low | High | Both classes |
|---|---|---|---|---|---|---|
| R00_S1_V1 | arousal | 19 | 14 | 2 | 12 | True |
| R00_S1_V2 | arousal | 9 | 6 | 1 | 5 | True |
| R00_S1_V3 | arousal | 5 | 5 | 3 | 2 | True |
| R00_S2_V1 | arousal | 19 | 15 | 9 | 6 | True |
| R00_S2_V2 | arousal | 6 | 5 | 4 | 1 | True |
| R00_S2_V3 | arousal | 8 | 7 | 6 | 1 | True |
| R00_S3_V1 | arousal | 14 | 9 | 3 | 6 | True |
| R00_S3_V2 | arousal | 6 | 6 | 2 | 4 | True |
| R00_S3_V3 | arousal | 4 | 4 | 3 | 1 | True |
| R00_S1_V1 | valence | 19 | 18 | 12 | 6 | True |
| R00_S1_V2 | valence | 9 | 7 | 3 | 4 | True |
| R00_S1_V3 | valence | 5 | 4 | 4 | 0 | False |
| R00_S2_V1 | valence | 19 | 18 | 13 | 5 | True |
| R00_S2_V2 | valence | 6 | 5 | 4 | 1 | True |
| R00_S2_V3 | valence | 8 | 7 | 6 | 1 | True |
| R00_S3_V1 | valence | 14 | 7 | 4 | 3 | True |
| R00_S3_V2 | valence | 6 | 6 | 4 | 2 | True |
| R00_S3_V3 | valence | 4 | 3 | 3 | 0 | False |

## Inner-joint model-selection capacity

| Repetition | Task | Inner configs | Operational rate | Min train rows | Min validation rows | Min legal donors | Max zero-donor rate |
|---|---|---|---|---|---|---|---|
| 0 | arousal | 36 | 0.5556 | 4 | 4 | 0 | 1.0000 |
| 0 | valence | 36 | 0.2222 | 4 | 4 | 0 | 0.4286 |
| 1 | arousal | 36 | 0.3333 | 7 | 7 | 0 | 0.4286 |
| 1 | valence | 36 | 0.3333 | 7 | 7 | 0 | 0.3333 |
| 2 | arousal | 36 | 0.4444 | 4 | 4 | 0 | 1.0000 |
| 2 | valence | 36 | 0.2778 | 4 | 4 | 0 | 1.0000 |
| 3 | arousal | 36 | 0.4722 | 1 | 1 | 0 | 1.0000 |
| 3 | valence | 36 | 0.3611 | 1 | 1 | 0 | 1.0000 |
| 4 | arousal | 36 | 0.3333 | 5 | 5 | 0 | 0.4286 |
| 4 | valence | 36 | 0.4722 | 5 | 5 | 0 | 0.5000 |

## Raw-XDF constructibility

- Raw scan mode: `RAW_XDF`
- Sessions audited: `30`
- Sessions with Raw-XDF loader errors: `0`
- Physical trials with at least two valid paired windows: `90 / 90`
- Valid paired-window count range: `20` to `53`

## Decision reasons

### Restrictions and cautions

- Some primary anchors have fewer than five legal donors.
- Some primary anchors have fewer than three donor subjects.
- Some primary anchors have fewer than three donor exact videos.
- Sensitivity repetitions do not maintain a five-donor minimum.
- Leakage-safe primary inner-joint training/validation is operational in fewer than 80% of configurations.
- Across frozen repetitions, inner-joint model-selection capacity is fragile.
- Primary test contains task-specific single-class cells; only pooled-repetition metrics are valid.
- At least one primary task-cell has fewer than five scored trials.
- Only 24 participants and 90 emotional physical trials are available in the strict paired cohort.
- The participant-by-exact-video graph is sparse and includes singleton-supported videos.
- Exact video is highly informative for Valence in diagnostic seen-video regions, so no stimulus-removal claim is allowed.
- Raw XDF does not contain Fz. The verified official mapping is F3->FP1, S2->FP2, S3->C3, S4->C4, S5->LE, S6->EOG1, S7->EOG2. The paper must report four scalp EEG channels, one left-ear reference, and two EOG channels rather than five scalp channels including Fz.

## Permitted interpretation

- PM-SSI may be described as paired provenance-preserving feature-statistics perturbation.
- A different exact-video donor is available only when recorded by this audit; no same-video fallback is allowed.
- Windows are computational views of one physical trial and are not independent samples.
- The method cannot claim direct removal or causal disentanglement of stimulus identity.
- If the verdict is YELLOW, all architecture and hyperparameters must be frozen on the main Paper-1 datasets before DEJA-VU is run.
- Repetition 0 remains primary; repetitions 1–4 remain sensitivity.

## Required outputs

- `docs/dejavu_pm_ssi_raw_window_constructibility.csv`
- `docs/dejavu_pm_ssi_donor_anchor_support.csv.gz`
- `docs/dejavu_pm_ssi_donor_cell_support.csv`
- `docs/dejavu_pm_ssi_donor_protocol_summary.csv`
- `docs/dejavu_pm_ssi_inner_joint_support.csv`
- `docs/dejavu_pm_ssi_outer_test_support.csv`
- `docs/dejavu_pm_ssi_final_qualification.md`
- `docs/dejavu_pm_ssi_final_qualification.json`
