
## G2 generator revisions (2026-10-16, before any model was scored on G2 programs)
- v1 (99ba36fd758b, ffc6344691d4, 47994d20d83d): Gate A 87.9%, stdin size unbalanced (SMD -0.40 lines, -0.31 tokens). Cause: input caps, name vocabulary exhaustion, strict resource limits on real programs.
- v2 (e0e14d2b1cda, 520306380887, c88e391b9579): Gate A 90.3%; Gate B failed on cc (+0.101), name_len_mean (-0.256), name_single_frac (+0.178). The 150 unmatched were deep programs (depth above 5).
- v3 (21ec3e1dce56): depth steering. Gate A 98.7%; names still failed Gate B (-0.229, +0.186).
- v3b (2f1e3bdb7c5f): name-length calibration (+0.6) and best-of-four selection. Gate A 98.96%, Gate B PASS (all matched covariates within threshold).
No model output was seen at any step. Revisions used: both allowed after v2.
