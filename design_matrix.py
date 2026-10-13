"""
CAFA design matrix: full 2^3 factorial over three EXECUTABLE factors.

=== WHY THREE FACTORS, AND WHAT HAPPENED TO THE OTHER TWO ===

CAFA began as a five-candidate study: memorization (X1, repository overlap),
lexical dependence (X2, identifiers), structural pattern-matching (X3, AST
structure), cross-language semantic reasoning (X4/X5, transpilation), and
benchmark artifact (X4, syntheticity). Two candidates were validated and
withdrawn before the executable design was fixed, not omitted silently:

  X1 (memorization). Requires a corpus straddling the model's training
  cutoff. CONFIRMED INFEASIBLE by direct measurement, not architectural
  inference: after joining official CodeNet submission metadata, 500/500
  dated samples fell pre-cutoff (100.0%). Project CodeNet predates the
  training cutoff of every locally-runnable code model; no slicing of the
  corpus produces a contrast.

  Cross-language transpilation (originally the design's fifth factor).
  Implemented, measured, and withdrawn: balanced coverage required
  restricting the pool to programs with median cyclomatic complexity 2 and
  median nesting depth 0 -- a construct-validity failure, not an
  engineering shortfall. See RESEARCH_PLAN.md and the paper's Preliminary
  Validation section for the measured progression.

The remaining three factors -- identifiers, AST structure, and
syntheticity -- were each validated by execution (0% measured corruption
after hardening) and share balanced, uniform coverage across the full pool.
They are retained under their ORIGINAL numbering (X2, X3, X4) rather than
renumbered to X1-X3, so that every reference in the paper and codebase to
"X2" or "X4" means the same intervention throughout -- a design history is
easier to audit than a design that quietly relabels itself.

2^3 = 8 conditions: no generator, no aliasing, every main effect and every
interaction up to the three-way term estimated exactly.
"""
from __future__ import annotations
import itertools
import numpy as np

FACTORS = ["identifiers", "ast_structure", "syntheticity"]
FACTOR_LABELS = {"identifiers": "X2", "ast_structure": "X3", "syntheticity": "X4"}

LEVEL_LABELS = {
    "identifiers":   {1: "original_names",  -1: "obfuscated_renamed"},
    "ast_structure": {1: "original_ast",    -1: "randomized_valid_ast"},
    "syntheticity":  {1: "real_world_code", -1: "synthetic_counterfactual"},
}


def build_design_matrix() -> np.ndarray:
    """(2^len(FACTORS), len(FACTORS)) array of +-1 coded conditions, full
    factorial. Column order matches FACTORS. No generator, no aliasing.
    Derived from len(FACTORS) rather than hardcoded, so dropping or adding a
    factor (as happened twice already: X4/transpilation, then X1/memorization)
    cannot silently leave a stale row count."""
    return np.array([list(row) for row in itertools.product([1, -1], repeat=len(FACTORS))])


def describe_matrix(matrix: np.ndarray) -> list[dict]:
    rows = []
    for i, row in enumerate(matrix):
        cond = {"condition_id": i + 1}
        for factor, level in zip(FACTORS, row):
            cond[factor] = LEVEL_LABELS[factor][int(level)]
        rows.append(cond)
    return rows


def print_markdown_table(matrix: np.ndarray) -> None:
    rows = describe_matrix(matrix)
    headers = ["Condition"] + [f.replace("_", " ").title() for f in FACTORS]
    print("| " + " | ".join(headers) + " |")
    print("|" + "---|" * len(headers))
    for r in rows:
        vals = [str(r["condition_id"])] + [r[f].replace("_", " ") for f in FACTORS]
        print("| " + " | ".join(vals) + " |")


def verify_design(matrix: np.ndarray) -> dict:
    """Orthogonality and balance checks. A full factorial should have every
    column orthogonal to every other, and every factor balanced 8/8."""
    checks = {"n_conditions": int(matrix.shape[0]), "n_factors": int(matrix.shape[1])}
    orth = {}
    for i, j in itertools.combinations(range(matrix.shape[1]), 2):
        orth[f"{FACTORS[i]}__{FACTORS[j]}"] = int(np.dot(matrix[:, i], matrix[:, j]))
    checks["pairwise_dot_products"] = orth
    checks["all_orthogonal"] = all(v == 0 for v in orth.values())
    checks["balanced"] = all(int(np.sum(matrix[:, k])) == 0 for k in range(matrix.shape[1]))
    checks["is_full_factorial"] = matrix.shape[0] == 2 ** matrix.shape[1]
    # Every interaction column must also be orthogonal to every main effect.
    inter_ok = True
    for r in range(2, matrix.shape[1] + 1):
        for subset in itertools.combinations(range(matrix.shape[1]), r):
            col = np.ones(matrix.shape[0])
            for idx in subset:
                col = col * matrix[:, idx]
            if r < matrix.shape[1] and int(np.sum(col)) != 0:
                inter_ok = False
    checks["interactions_orthogonal"] = inter_ok
    return checks


if __name__ == "__main__":
    dm = build_design_matrix()
    print("CAFA 2^3 full factorial design matrix (8 conditions)\n")
    print_markdown_table(dm)
    print("\nValidity checks:")
    for k, v in verify_design(dm).items():
        print(f"  {k}: {v}")