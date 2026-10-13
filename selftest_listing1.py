#!/usr/bin/env python3
"""
selftest_listing1.py -- estimator self-test for Listing 1 (synthetic data, known ground truth).

Injects, on the 2^3 design, in response units (perturbed minus baseline): identifiers main
effect -0.35, identifiers x ast_structure difference-in-differences -0.20, syntheticity main
effect -0.03, on a 0.65 baseline (responses stay inside [0,1]), with Gaussian replicate noise.
Decomposes with the patched sobol_anova and prints all 7 terms (3 main, 3 two-way, 1 three-way).
Run from the directory that contains sobol_anova.py and design_matrix.py.
"""
import itertools
import numpy as np
from design_matrix import build_design_matrix, FACTORS
from sobol_anova import effect_contrast, sobol_indices

rng = np.random.default_rng(0)
dm = build_design_matrix()                       # (8, 3), +-1 coded, rows = C1..C8
n_reps = 8
# coefficient on +-1 coding: main effect / 2, two-way difference-in-differences / 4
b_id, b_int, b_syn = -0.35 / 2, -0.20 / 4, -0.03 / 2
y = np.zeros((8, n_reps))
for r, row in enumerate(dm):
    mu = 0.65 + b_id * row[0] + b_syn * row[2] + b_int * row[0] * row[1]
    y[r] = np.clip(mu + rng.normal(0, 0.01, n_reps), 0, 1)

res = sobol_indices(dm, y)
means = y.mean(1)
print("CAFA estimator self-test (synthetic responses, known injected structure)\n")
print("Main effects and total-order indices (% of between-condition variance)")
for f, v in res["per_factor"].items():
    print(f"  {f:15s} S_i={v['S_i_percent']:6.2f}%   S_Ti={v['S_Ti_approx_percent']:6.2f}%")
print("\nFull interaction table, no aliasing (% of between-condition variance)")
ss_tot = res["ss_total"]
rows = []
for k in (1, 2, 3):
    for sub in itertools.combinations(range(3), k):
        ss = effect_contrast(dm, means, sub)[2]
        rows.append((" x ".join(FACTORS[i] for i in sub), ss / ss_tot * 100))
for name, pct in rows:
    print(f"  {name:42s} {pct:6.2f}%")
print(f"  {'sum of all seven terms':42s} {sum(p for _, p in rows):6.2f}%")
