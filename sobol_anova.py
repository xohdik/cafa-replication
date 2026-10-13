"""
Closed-form Sobol-index / functional-ANOVA decomposition for the CAFA
2^k full factorial design (k = len(FACTORS); k = 3 in the executable design).

This is classical factorial-design ANOVA (Montgomery, "Design and Analysis
of Experiments"), algebraically equivalent to Sobol indices for orthogonal
+-1-coded designs -- NOT Monte-Carlo Sobol sampling (Saltelli/SALib), which
assumes a cheap-to-sample simulator rather than sixteen expensive real
experiments. State this distinction explicitly in the methods section.

KEY IMPLEMENTATION IDEA: because the design's 5th column is literally the
elementwise product of the other four (X5 = X1*X2*X3*X4, the generator
relation), computing "the effect of subset S" as the dot product of the
*actual* signed column-product for S with the response vector automatically
and correctly returns identical numbers for aliased subsets (e.g. the
contrast for {5} and the contrast for {1,2,3,4} will come out numerically
identical, because their sign columns are numerically identical by
construction). This means alias bookkeeping does not need to be hand-coded
separately -- it falls out of using the real design matrix.
"""
import itertools
import numpy as np

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from design_matrix import build_design_matrix, FACTORS


def effect_contrast(design: np.ndarray, response: np.ndarray, subset: tuple[int, ...]):
    """subset: 0-indexed factor indices, e.g. (0,) for X1 main effect,
    (0, 1) for the X1*X2 interaction contrast.
    Returns (contrast, effect_estimate, sum_of_squares)."""
    col = np.ones(design.shape[0])
    for idx in subset:
        col = col * design[:, idx]
    contrast = float(np.dot(col, response))
    n_runs = design.shape[0]
    effect = 2 * contrast / n_runs
    ss = contrast ** 2 / n_runs
    return contrast, effect, ss


def sobol_indices(design: np.ndarray, response_matrix: np.ndarray) -> dict:
    """
    response_matrix: (n_conditions, n_reps) array -- one row per design condition,
    one column per bootstrap/seed replicate.

    Returns a dict with per-factor S_i, the aliasing-approximated S_Ti
    (= S_i + all estimable 2-way interactions involving i), and the raw
    2-way interaction table so the alias structure is auditable.
    """
    means = response_matrix.mean(axis=1)          # (n_conditions,) condition means
    # Between-condition sum of squares of the condition means. The numerators below
    # are built from the means, so the denominator must be in the same units.
    # (Summing over every replicate deflated each share by the replicate count.)
    ss_total = float(np.sum((means - means.mean()) ** 2))
    if ss_total == 0:
        raise ValueError("Zero total variance in response -- check input data.")

    n_factors = design.shape[1]
    ss_main = {i: effect_contrast(design, means, (i,))[2] for i in range(n_factors)}
    ss_2way = {(i, j): effect_contrast(design, means, (i, j))[2]
               for i, j in itertools.combinations(range(n_factors), 2)}

    per_factor = {}
    for i in range(n_factors):
        Si = ss_main[i] / ss_total * 100
        interacting = sum(ss for (a, b), ss in ss_2way.items() if i in (a, b))
        STi_approx = (ss_main[i] + interacting) / ss_total * 100
        per_factor[FACTORS[i]] = {
            "S_i_percent": round(Si, 2),
            "S_Ti_approx_percent": round(STi_approx, 2),
            "interactive_share_percent": round(STi_approx - Si, 2),
        }

    interaction_table = {
        f"{FACTORS[i]} x {FACTORS[j]}": round(ss / ss_total * 100, 2)
        for (i, j), ss in ss_2way.items()
    }

    return {
        "per_factor": per_factor,
        "two_way_interactions_percent": interaction_table,
        "ss_total": ss_total,
        "note": "S_Ti_approx assumes 3-way-and-higher interactions are "
                "negligible (standard Resolution-V assumption, must be "
                "stated explicitly in the paper -- see RESEARCH_PLAN.md 4).",
    }


def bootstrap_ci(design: np.ndarray, response_matrix: np.ndarray,
                  n_boot: int = 1000, seed: int = 0) -> dict:
    """Percentile bootstrap CIs on each factor's S_i by resampling replicate
    columns with replacement, condition by condition.

    WARNING: this resamples replicates only, so it captures decoding noise and
    nothing else. Under greedy decoding replicates are near-duplicates and the
    interval is far too narrow. Report program-level intervals from
    cafa_shares.py instead.
    """
    rng = np.random.default_rng(seed)
    n_conditions, n_reps = response_matrix.shape
    boot_Si = {f: [] for f in FACTORS}

    for _ in range(n_boot):
        resampled = np.empty_like(response_matrix)
        for c in range(n_conditions):
            idx = rng.integers(0, n_reps, size=n_reps)
            resampled[c] = response_matrix[c, idx]
        try:
            result = sobol_indices(design, resampled)
        except ValueError:
            continue
        for f in FACTORS:
            boot_Si[f].append(result["per_factor"][f]["S_i_percent"])

    ci = {}
    for f in FACTORS:
        arr = np.array(boot_Si[f])
        ci[f] = {
            "S_i_median": round(float(np.median(arr)), 2),
            "S_i_ci_lower_2.5": round(float(np.percentile(arr, 2.5)), 2),
            "S_i_ci_upper_97.5": round(float(np.percentile(arr, 97.5)), 2),
        }
    return ci


if __name__ == "__main__":
    # Synthetic demo data ONLY -- not real experimental results. Structure:
    # baseline performance around 0.7, with engineered main effects so the
    # pipeline's output can be sanity-checked against known ground truth.
    rng = np.random.default_rng(0)
    dm = build_design_matrix()
    n_reps = 8

    # Ground truth for the demo: memorization (idx 0) and language (idx 3)
    # have real main effects; identifiers (idx 1) and language interact.
    n_factors = dm.shape[1]
    true_effects = np.array([0.08, 0.02, 0.01, 0.06])[:n_factors]
    interaction_12 = 0.05  # identifiers x syntheticity interaction (synthetic)

    responses = np.zeros((dm.shape[0], n_reps))
    for row_idx, row in enumerate(dm):
        base = 0.70
        base += sum(true_effects[i] * row[i] for i in range(n_factors))
        base += interaction_12 * row[1] * row[min(3, n_factors - 1)]
        noise = rng.normal(0, 0.01, size=n_reps)
        responses[row_idx] = np.clip(base + noise, 0, 1)

    result = sobol_indices(dm, responses)
    print("Per-factor decomposition (SYNTHETIC DEMO DATA):\n")
    for factor, vals in result["per_factor"].items():
        print(f"  {factor:15s}  S_i={vals['S_i_percent']:6.2f}%   "
              f"S_Ti(approx)={vals['S_Ti_approx_percent']:6.2f}%   "
              f"interactive={vals['interactive_share_percent']:6.2f}%")

    print("\nTwo-way interaction table (% of total variance):")
    for pair, pct in result["two_way_interactions_percent"].items():
        print(f"  {pair:40s} {pct:6.2f}%")

    print("\nBootstrap CIs on S_i (200 resamples, demo speed):")
    ci = bootstrap_ci(dm, responses, n_boot=200, seed=1)
    for f, v in ci.items():
        print(f"  {f:15s}  median={v['S_i_median']:6.2f}%  "
              f"[{v['S_i_ci_lower_2.5']:6.2f}, {v['S_i_ci_upper_97.5']:6.2f}]")