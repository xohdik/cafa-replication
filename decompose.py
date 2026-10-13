"""
Decompose a scored response matrix into per-factor contributions.

This is the last step of the pipeline: it takes the accuracy matrix produced
by scoring_harness.py and reports S_i, S_Ti, the pairwise interaction table,
and bootstrap confidence intervals -- then emits the numbers in a form that
drops straight into the paper's figure.

Because the design is a full 2^4 factorial rather than a fraction, S_Ti is
exact here: every interaction up to the four-way term is estimated without
aliasing, so no negligible-higher-order assumption is required.

Usage:
    python3 analysis/decompose.py --responses responses.json
    python3 analysis/decompose.py --responses responses.json --latex
"""
import argparse
import itertools
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from design_matrix import build_design_matrix, FACTORS
from sobol_anova import effect_contrast, sobol_indices, bootstrap_ci

# Human-readable names for what each switch is meant to isolate.
FACTOR_MEANING = {
    "repo_overlap":  "memorization",
    "identifiers":   "lexical dependence",
    "ast_structure": "structural pattern-matching",
    "syntheticity":  "benchmark artifact",
}


def load_matrix(path: str) -> np.ndarray:
    with open(path) as f:
        result = json.load(f)
    cids = sorted(result["response_matrix"], key=int)
    rows = []
    missing = []
    for cid in cids:
        row = result["response_matrix"][cid]
        if any(v is None for v in row):
            missing.append(cid)
        else:
            rows.append(row)
    if missing:
        raise SystemExit(
            f"Conditions {missing} have unscored replicates. The decomposition "
            f"needs every cell populated; a missing cell is not a zero. Check "
            f"the skip count in {path} and the manifest audit.")
    return np.array(rows), result


def full_interaction_table(design: np.ndarray, means: np.ndarray) -> dict:
    """Every interaction order, not just pairwise -- available because the
    design is full rather than fractional."""
    ss_total = float(np.sum((means - means.mean()) ** 2))
    out = {}
    n = design.shape[1]
    for r in range(2, n + 1):
        for subset in itertools.combinations(range(n), r):
            _, _, ss = effect_contrast(design, means, subset)
            name = " x ".join(FACTORS[i] for i in subset)
            out[name] = (ss / ss_total * 100) if ss_total else 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", required=True)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--latex", action="store_true",
                    help="Emit pgfplots coordinates for the paper figure.")
    args = ap.parse_args()

    matrix, raw = load_matrix(args.responses)
    design = build_design_matrix()

    if matrix.shape[0] != design.shape[0]:
        raise SystemExit(f"Response matrix has {matrix.shape[0]} conditions, "
                          f"design has {design.shape[0]}.")

    result = sobol_indices(design, matrix)
    means = matrix.mean(axis=1)

    print("=" * 72)
    print("CAPABILITY DECOMPOSITION")
    print("=" * 72)
    print(f"  conditions: {matrix.shape[0]}   replicates: {matrix.shape[1]}")
    print(f"  overall accuracy: {means.mean():.3f} "
          f"(range {means.min():.3f}-{means.max():.3f})")
    print(f"  baseline (all-original) accuracy: {means[0]:.3f}")

    print("\n" + "=" * 72)
    print("PER-FACTOR CONTRIBUTIONS")
    print("=" * 72)
    print(f"  {'factor':<16} {'isolates':<28} {'S_i':>8} {'S_Ti':>8} {'inter':>8}")
    print("  " + "-" * 70)
    for f in FACTORS:
        v = result["per_factor"][f]
        print(f"  {f:<16} {FACTOR_MEANING[f]:<28} "
              f"{v['S_i_percent']:>7.2f}% {v['S_Ti_approx_percent']:>7.2f}% "
              f"{v['interactive_share_percent']:>7.2f}%")

    print("\n" + "=" * 72)
    print("INTERACTIONS (all orders; exact, no aliasing)")
    print("=" * 72)
    inter = full_interaction_table(design, means)
    for name, pct in sorted(inter.items(), key=lambda kv: -kv[1]):
        if pct >= 0.01:
            order = name.count(" x ") + 1
            flag = "  <-- high order, likely noise" if order >= 3 and pct > 1.0 else ""
            print(f"  {name:<52} {pct:>6.2f}%{flag}")
    print()
    print("  NOTE: with a full factorial, high-order interaction terms absorb")
    print("  sampling variance when cells contain few samples. In a validation")
    print("  run with a known generating model and no injected four-way effect,")
    print("  the four-way term still registered 4.3%. Treat three- and four-way")
    print("  terms as noise unless the bootstrap interval excludes zero and the")
    print("  per-cell sample count is large.")

    print("\n" + "=" * 72)
    print(f"BOOTSTRAP CONFIDENCE INTERVALS ({args.boot} resamples)")
    print("=" * 72)
    ci = bootstrap_ci(design, matrix, n_boot=args.boot, seed=0)
    for f in FACTORS:
        v = ci[f]
        print(f"  {f:<16} S_i = {v['S_i_median']:5.2f}%  "
              f"[{v['S_i_ci_lower_2.5']:5.2f}, {v['S_i_ci_upper_97.5']:5.2f}]")

    print("\n" + "=" * 72)
    print("READING THESE NUMBERS")
    print("=" * 72)
    print("  S_i is the variance in measured accuracy attributable to that")
    print("  switch alone; S_Ti adds every interaction involving it. The gap")
    print("  between them is variance that cannot be assigned to one factor,")
    print("  and it is the quantity sequential ablation silently allocates to")
    print("  whichever intervention ran first.")
    print()
    print("  A small S_i means performance did not move much when that switch")
    print("  was flipped. Before reading that as a claim about the model,")
    print("  check the operator's coverage in the manifest audit: a factor")
    print("  applied to few samples attenuates its own effect.")

    if args.latex:
        print("\n" + "=" * 72)
        print("PGFPLOTS COORDINATES (paste into the paper's Sobol figure)")
        print("=" * 72)
        label = {"repo_overlap": "Memorization", "identifiers": "Lexical",
                 "ast_structure": "Structural", "syntheticity": "Artifact"}
        si = " ".join(f"({label[f]},{result['per_factor'][f]['S_i_percent']:.1f})"
                      for f in FACTORS)
        sti = " ".join(f"({label[f]},{result['per_factor'][f]['S_Ti_approx_percent']:.1f})"
                       for f in FACTORS)
        print(f"  % S_i series\n  {si}")
        print(f"  % S_Ti series\n  {sti}")


if __name__ == "__main__":
    main()