
## G2 generator revisions (2026-10-16, before any model was scored on G2 programs)
- v1 (99ba36fd758b, ffc6344691d4, 47994d20d83d): Gate A 87.9%, stdin size unbalanced (SMD -0.40 lines, -0.31 tokens). Cause: input caps, name vocabulary exhaustion, strict resource limits on real programs.
- v2 (e0e14d2b1cda, 520306380887, c88e391b9579): Gate A 90.3%; Gate B failed on cc (+0.101), name_len_mean (-0.256), name_single_frac (+0.178). The 150 unmatched were deep programs (depth above 5).
- v3 (21ec3e1dce56): depth steering. Gate A 98.7%; names still failed Gate B (-0.229, +0.186).
- v3b (2f1e3bdb7c5f): name-length calibration (+0.6) and best-of-four selection. Gate A 98.96%, Gate B PASS (all matched covariates within threshold).
No model output was seen at any step. Revisions used: both allowed after v2.

## G2 manifest and Gate C (2026-10-16, before any model was scored on G2 programs)
- manifest_g2.json sha256 36a51e524f0568687606d63a0cadaa81f1507e89ce0d87601a150d9ecbc23637; 1,526 samples (the 1,526 matched at Gate A), conditions 2, 4, 6, 8. PREREG_G2.md states 1,542 samples per cell; the experiments use 1,526 (E1 = 30,520 generations) because 16 long programs were not matched. They are reported in the selection check.
- Gate C passed: 0 run failures, 0 output mismatches across the four conditions on three stdin cases. 0 of 3,052 shuffles reverted, but only 665 of 1,526 shuffles per I level changed the code (the rest had nothing independent to reorder).

## G2 experiments (2026-10-18)
- E1/E2/E3 run on manifest_g2.json (1,526 samples; 1,525 with all eight cells). g2_analyze.py implements H1 to H3 exactly as in PREREG_G2.md, except that the Holm family for H3 (five models' G2 source-by-prompt p-values) was not named in the pre-registration and was chosen when the script was written, before any result was seen.
- g2_posthoc_outlen.py is POST HOC (written after seeing that G2 accuracy is 8 to 13 percent against 20 to 34 for real programs and that G2 outputs are longer than real ones).
