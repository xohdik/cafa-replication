"""
RQ2 (model generality): do capability contributions differ across model
families? Compares two (or more) models' Sobol decompositions and tests
whether each factor's S_i genuinely differs, not just eyeballing two numbers
side by side.

Self-contained rather than importing analysis/sobol_anova.py or decompose.py
directly: the working decompose.py has evolved on the R740 independently of
this sandbox (different file layout, possible fixes not synced back here),
so importing it risks a version mismatch. This embeds its own copy of the
same, already-tested Sobol math instead, verified against the shape of
result every previous decompose.py run in this project has produced.

Usage:
    python3 compare_models.py --responses responses_deepseek.json:DeepSeek-Coder-6.7B \\
        responses_qwen.json:Qwen2.5-Coder-7B
"""
from __future__ import annotations
import argparse
import itertools
import json
import sys
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from design_matrix import build_design_matrix, FACTORS


def effect_contrast(design: np.ndarray, response: np.ndarray, subset: tuple):
    col = np.ones(design.shape[0])
    for idx in subset:
        col = col * design[:, idx]
    contrast = float(np.dot(col, response))
    n_runs = design.shape[0]
    return contrast ** 2 / n_runs  # sum of squares


def sobol_si(design: np.ndarray, response_matrix: np.ndarray) -> dict:
    """response_matrix: (n_conditions, n_reps). Returns {factor: S_i_percent}."""
    means = response_matrix.mean(axis=1)
    all_obs = response_matrix.flatten()
    ss_total = float(np.sum((all_obs - all_obs.mean()) ** 2))
    if ss_total == 0:
        return {f: 0.0 for f in FACTORS}
    n_factors = design.shape[1]
    return {
        FACTORS[i]: effect_contrast(design, means, (i,)) / ss_total * 100
        for i in range(n_factors)
    }


def load_response_matrix(path: str) -> np.ndarray:
    """Reconstruct the (n_conditions, n_reps) array from a scoring_harness.py
    output file's response_matrix field."""
    data = json.load(open(path))
    rm = data["response_matrix"]
    cids = sorted(rm, key=int)
    rows = []
    for cid in cids:
        row = rm[cid]
        if any(v is None for v in row):
            raise ValueError(
                f"{path}: condition {cid} has a missing (None) replicate -- "
                f"cannot decompose with an incomplete cell. Check n_skipped "
                f"in this file before comparing models.")
        rows.append(row)
    return np.array(rows)


def bootstrap_difference(design, matrix_a, matrix_b, n_boot=2000, seed=0):
    """Resample both models' replicate columns independently, compute
    S_i(A) - S_i(B) per factor per resample, and report the percentile CI
    on the DIFFERENCE. A CI that excludes zero is real evidence the models
    differ on that factor, not just two numbers that happen to differ."""
    rng = np.random.default_rng(seed)
    n_cond_a, n_reps_a = matrix_a.shape
    n_cond_b, n_reps_b = matrix_b.shape
    diffs = {f: [] for f in FACTORS}

    for _ in range(n_boot):
        resampled_a = np.empty_like(matrix_a)
        for c in range(n_cond_a):
            idx = rng.integers(0, n_reps_a, size=n_reps_a)
            resampled_a[c] = matrix_a[c, idx]
        resampled_b = np.empty_like(matrix_b)
        for c in range(n_cond_b):
            idx = rng.integers(0, n_reps_b, size=n_reps_b)
            resampled_b[c] = matrix_b[c, idx]

        si_a = sobol_si(design, resampled_a)
        si_b = sobol_si(design, resampled_b)
        for f in FACTORS:
            diffs[f].append(si_a[f] - si_b[f])

    result = {}
    for f in FACTORS:
        arr = np.array(diffs[f])
        lo, hi = np.percentile(arr, [2.5, 97.5])
        result[f] = {
            "diff_median": float(np.median(arr)),
            "ci_lower": float(lo),
            "ci_upper": float(hi),
            "significant": bool(lo > 0 or hi < 0),
        }
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--responses", nargs="+", required=True,
                     help="path:label pairs, e.g. responses_a.json:ModelA "
                          "responses_b.json:ModelB. Exactly 2 for now.")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if len(args.responses) != 2:
        print("Currently supports exactly 2 models per comparison. "
              "Run pairwise for more.")
        sys.exit(1)

    entries = []
    for spec in args.responses:
        path, label = spec.rsplit(":", 1)
        entries.append((path, label))

    design = build_design_matrix()

    matrices = {}
    si_results = {}
    for path, label in entries:
        m = load_response_matrix(path)
        matrices[label] = m
        si_results[label] = sobol_si(design, m)
        print(f"Loaded {label}: {path} -- {m.shape[0]} conditions x {m.shape[1]} reps")

    print()
    print("=" * 78)
    print("PER-FACTOR S_i COMPARISON")
    print("=" * 78)
    labels = [label for _, label in entries]
    header = f"{'factor':<16}" + "".join(f"{l:>20}" for l in labels) + f"{'diff':>14}"
    print(header)
    print("-" * len(header))
    for f in FACTORS:
        vals = [si_results[l][f] for l in labels]
        diff = vals[0] - vals[1]
        row = f"{f:<16}" + "".join(f"{v:>19.2f}%" for v in vals) + f"{diff:>13.2f}%"
        print(row)

    print()
    print("=" * 78)
    print(f"BOOTSTRAP TEST ON THE DIFFERENCE ({args.n_boot} resamples)")
    print("=" * 78)
    diff_result = bootstrap_difference(design, matrices[labels[0]], matrices[labels[1]],
                                        n_boot=args.n_boot, seed=args.seed)
    for f in FACTORS:
        d = diff_result[f]
        sig = "SIGNIFICANT" if d["significant"] else "not significant"
        print(f"  {f:<16} diff={d['diff_median']:>7.2f}%  "
              f"[{d['ci_lower']:>7.2f}, {d['ci_upper']:>7.2f}]  {sig}")

    print()
    print("INTERPRETATION")
    any_sig = any(diff_result[f]["significant"] for f in FACTORS)
    if any_sig:
        sig_factors = [f for f in FACTORS if diff_result[f]["significant"]]
        print(f"  {', '.join(sig_factors)} show a bootstrap-confirmed difference")
        print(f"  between {labels[0]} and {labels[1]} -- this is real evidence for")
        print(f"  RQ2 (contributions differ across model families), not just two")
        print(f"  point estimates that happen not to match.")
    else:
        print(f"  No factor's difference CI excludes zero. On this evidence, the")
        print(f"  two models' capability decompositions are not distinguishable --")
        print(f"  a genuine answer to RQ2, not a null result to hide.")


if __name__ == "__main__":
    main()