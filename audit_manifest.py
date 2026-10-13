"""
Manifest audit: verify that every condition in the full factorial design
actually received the treatment it is supposed to encode, BEFORE any model
is run.

WHY THIS EXISTS. A silent design failure was found by accident during
orchestrator development: synthetic samples carried no test inputs, X3
(AST shuffle) refuses to shuffle code it cannot behaviorally verify, and 4
of the 8 shuffle conditions are also synthetic (3, 8, 12, 15). Half the X3
cells were therefore receiving no X3 treatment at all. Nothing in the output
said so. The factorial contrast for X3 would have been computed over cells
that were not actually differentiated, biasing S_i(structure) toward zero
for a purely mechanical reason.

That class of failure is invisible in results and cheap to detect in
advance, so it should never be found by accident twice. This audit answers:
for each condition, how many samples actually got each treatment, how many
silently reverted, and how many were skipped.

CRITICAL DISTINCTION the audit enforces: uniform loss is tolerable, uneven
loss is not. If X3 applies to 80% of samples in EVERY shuffle condition,
the contrast is still valid (attenuated, but unbiased). If X3 applies to
100% in condition 7 and 50% in condition 3, the X3 contrast is confounded
with whatever else differs between those cells. The audit therefore reports
per-condition rates AND the spread across cells sharing a factor level.

Usage:
    python3 audit_manifest.py --manifest manifest.json
    python3 audit_manifest.py --manifest manifest.json --max-spread 0.10
"""
from __future__ import annotations
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from design_matrix import build_design_matrix, describe_matrix, FACTORS

# Short +-1 codes for the compact table.
LEVEL_CODE = {
    "original_names": 0, "obfuscated_renamed": 1,
    "original_ast": 0, "randomized_valid_ast": 1,
    "original_lang": 0, "cross_transpiled": 1,
    "real_world_code": 0, "synthetic_counterfactual": 1,
}


def _check_manifest_matches_current_design(manifest: dict) -> None:
    """Fail loudly and specifically, rather than with a bare KeyError, when
    the manifest was built by a different version of the codebase than this
    script expects.

    DELIBERATELY HARDCODED rather than derived from `FACTORS` (imported from
    design_matrix.py). The first version of this guard used the import as
    its reference point and was fooled by exactly the case it exists to
    catch: design_matrix.py itself was stale, so the import and the
    manifest were consistently wrong TOGETHER, and the guard found nothing
    to disagree with -- it crashed one function later instead, on
    LEVEL_CODE having no entry for the old 'original_repo' label. A check
    that trusts the same supply chain it is verifying is not a check.
    This list is the ground truth regardless of what any local file says."""
    EXPECTED_FACTORS = ["identifiers", "ast_structure", "syntheticity"]
    EXPECTED_N_CONDITIONS = 8
    STALE_MARKERS = {"repo_overlap", "language"}

    if not manifest.get("samples"):
        return
    first_conditions = manifest["samples"][0].get("conditions", [])
    if not first_conditions:
        return

    n_seen = len(first_conditions)
    ops_seen = set()
    for c in first_conditions:
        for step in c.get("log", {}).get("steps", []):
            if step.get("op"):
                ops_seen.add(step["op"])

    imported_factors_stale = set(FACTORS) != set(EXPECTED_FACTORS)
    stale_ops = ops_seen & STALE_MARKERS
    missing_ops = set(EXPECTED_FACTORS) - ops_seen

    if n_seen != EXPECTED_N_CONDITIONS or stale_ops or missing_ops or imported_factors_stale:
        print("=" * 66)
        print("MANIFEST / CODE VERSION MISMATCH -- refusing to proceed")
        print("=" * 66)
        print(f"  Expected {EXPECTED_N_CONDITIONS} conditions/sample "
              f"(factors: {EXPECTED_FACTORS}); manifest has {n_seen}.")
        if stale_ops:
            print(f"  Stale operators found in the manifest: {sorted(stale_ops)}")
        if missing_ops:
            print(f"  Expected current factors missing from the manifest: {sorted(missing_ops)}")
        if imported_factors_stale:
            print(f"  design_matrix.py's own FACTORS is stale: {FACTORS}")
            print("  (this means design_matrix.py itself needs re-copying, not just")
            print("   orchestrator.py -- the two must always be replaced together)")
        print()
        print("  Likely cause: the local cafa/ directory has an old snapshot of")
        print("  multiple files together, not one stale file. Re-copy ALL of:")
        print("  orchestrator.py, design_matrix.py, audit_manifest.py from the")
        print("  latest output, run preflight_check.py, confirm PASS, THEN")
        print("  rebuild the manifest from scratch.")
        raise SystemExit(1)


def audit(manifest: dict) -> dict:
    _check_manifest_matches_current_design(manifest)
    conditions = describe_matrix(build_design_matrix())
    by_cond = {c["condition_id"]: {
        "levels": [LEVEL_CODE[c[f]] for f in FACTORS],
        "spec": c,
        "n": 0, "n_ok": 0, "n_failed": 0,
        # X3
        "x3_expected": c["ast_structure"] == "randomized_valid_ast",
        "x3_applied": 0, "x3_reverted": 0, "x3_skipped": 0, "x3_unverified": 0,
        # X2 / X4(syntheticity)
        "x2_expected": c["identifiers"] == "obfuscated_renamed",
        "x2_applied": 0,
        "x4_expected": c["syntheticity"] == "synthetic_counterfactual",
        "x4_applied": 0,
    } for c in conditions}

    for s in manifest.get("samples", []):
        for built in s.get("conditions", []):
            cid = built["condition_id"]
            rec = by_cond.get(cid)
            if rec is None:
                continue
            rec["n"] += 1
            if built.get("status") == "ok":
                rec["n_ok"] += 1
            else:
                rec["n_failed"] += 1

            for step in built.get("log", {}).get("steps", []):
                op, val = step.get("op"), step.get("value")
                if op == "ast_structure":
                    if step.get("reverted"):
                        rec["x3_reverted"] += 1
                    elif val == "SKIPPED":
                        rec["x3_skipped"] += 1
                    elif val == "shuffled":
                        rec["x3_applied"] += 1
                        if step.get("verified") is False:
                            rec["x3_unverified"] += 1
                elif op == "identifiers" and val == "obfuscated":
                    rec["x2_applied"] += 1
                elif op == "syntheticity" and val == "synthetic":
                    rec["x4_applied"] += 1

    return by_cond


def _rate(applied, n):
    return (applied / n) if n else 0.0


def check_balance(by_cond: dict, factor_key: str, applied_key: str,
                   expected_key: str, max_spread: float,
                   min_coverage: float = 0.30) -> dict:
    """Compare application rates across all conditions where the factor is
    switched ON. Uneven rates confound that factor's contrast.

    Two independent failure modes are checked, because a spread test alone is
    not sufficient:

    1. UNEVEN coverage -> the contrast is confounded with whatever differs
       between high- and low-coverage cells.
    2. UNIFORMLY NEAR-ZERO coverage -> the contrast is computed from almost no
       treated samples. This passes a spread test trivially (0% and 5% differ
       by 5%, well inside any sane spread limit) while being useless. A real
       run hit exactly this: X4 coverage of 0-5% across eight cells was
       reported as balanced and PASS, when in truth one sample out of 160 had
       received the treatment."""
    rates = {cid: _rate(r[applied_key], r["n"])
             for cid, r in by_cond.items() if r[expected_key] and r["n"]}
    if not rates:
        return {"factor": factor_key, "n_cells": 0, "ok": True,
                "note": "no cells with this factor on, or no samples"}
    lo, hi = min(rates.values()), max(rates.values())
    spread = hi - lo
    mean_rate = sum(rates.values()) / len(rates)
    balanced = spread <= max_spread
    sufficient = mean_rate >= min_coverage
    return {
        "factor": factor_key,
        "n_cells": len(rates),
        "min_rate": lo, "max_rate": hi, "spread": spread, "mean_rate": mean_rate,
        "min_cell": min(rates, key=rates.get), "max_cell": max(rates, key=rates.get),
        "balanced": balanced, "sufficient": sufficient,
        "ok": balanced and sufficient,
        "rates": rates,
    }


def print_report(by_cond: dict, max_spread: float = 0.10,
                  min_coverage: float = 0.30):
    print("=" * 74)
    print("MANIFEST AUDIT -- design coverage per condition")
    print("=" * 74)
    print("\nFactor levels: 0 = baseline (original/real), 1 = perturbed\n")
    hdr = f"{'Cond':>4}  {'X2':>2} {'X3':>2} {'X4':>2}  {'N':>5}  {'ok':>5}  {'fail':>5}"
    print(hdr)
    print("-" * len(hdr))
    for cid in sorted(by_cond):
        r = by_cond[cid]
        lv = r["levels"]
        print(f"{cid:>4}  {lv[0]:>2} {lv[1]:>2} {lv[2]:>2}  "
              f"{r['n']:>5}  {r['n_ok']:>5}  {r['n_failed']:>5}")

    # ---- X3 detail ----
    print("\n" + "=" * 74)
    print("X3 (AST shuffle) treatment coverage -- shuffle conditions only")
    print("=" * 74)
    hdr = f"{'Cond':>4}  {'N':>5}  {'applied':>8} {'reverted':>9} {'skipped':>8}  {'rate':>6}  {'unverif':>8}"
    print(hdr); print("-" * len(hdr))
    for cid in sorted(by_cond):
        r = by_cond[cid]
        if not r["x3_expected"]:
            continue
        rate = _rate(r["x3_applied"], r["n"])
        flag = "  <-- LOW" if rate < 0.5 else ""
        warn = "  <-- UNVERIFIED" if r["x3_unverified"] else ""
        print(f"{cid:>4}  {r['n']:>5}  {r['x3_applied']:>8} {r['x3_reverted']:>9} "
              f"{r['x3_skipped']:>8}  {rate:>5.1%}  {r['x3_unverified']:>8}{flag}{warn}")

    # ---- balance checks ----
    print("\n" + "=" * 74)
    print("BALANCE CHECKS -- uneven treatment across cells confounds a contrast")
    print("=" * 74)
    checks = [
        check_balance(by_cond, "X2 identifiers", "x2_applied", "x2_expected", max_spread, min_coverage),
        check_balance(by_cond, "X3 ast_structure", "x3_applied", "x3_expected", max_spread, min_coverage),
        check_balance(by_cond, "X4 syntheticity", "x4_applied", "x4_expected", max_spread, min_coverage),
    ]
    all_ok = True
    zero_coverage = []
    for c in checks:
        if c["n_cells"] == 0:
            print(f"  [SKIP] {c['factor']:<20} {c['note']}")
            continue
        # A factor applied to NOTHING is not "balanced" -- it is absent. Zero
        # everywhere trivially satisfies a spread test while making the
        # factor's contrast a comparison of identical cells, so it must be
        # reported separately rather than passing quietly.
        if not c["sufficient"]:
            zero_coverage.append(f"{c['factor']} (mean {c['mean_rate']:.1%})")
            all_ok = False
            label = "ZERO" if c["max_rate"] == 0.0 else "SPARSE"
            print(f"  [{label}] {c['factor']:<20} mean coverage {c['mean_rate']:.1%} "
                  f"(range {c['min_rate']:.1%}-{c['max_rate']:.1%}), need >={min_coverage:.0%}")
            continue
        status = "PASS" if c["ok"] else "FAIL"
        all_ok = all_ok and c["ok"]
        print(f"  [{status}] {c['factor']:<20} rate {c['min_rate']:.1%}-{c['max_rate']:.1%} "
              f"across {c['n_cells']} cells (spread {c['spread']:.1%}, limit {max_spread:.0%})")
        if not c["ok"]:
            print(f"         lowest: condition {c['min_cell']}, highest: condition {c['max_cell']}")

    print("\n" + "=" * 74)
    print("VERDICT")
    print("=" * 74)
    if zero_coverage:
        print(f"  FAIL -- insufficient coverage: {', '.join(zero_coverage)}.")
        print("  At this rate the contrast is computed from almost no treated")
        print("  samples, so the corresponding S_i is not small -- it is")
        print("  uninformative. Note that a spread test alone would PASS this,")
        print("  since 0% and 5% are 'balanced'; coverage and balance are")
        print("  separate requirements. Either the operator is unconfigured, or")
        print("  it is failing on this corpus and its feasibility should be")
        print("  reported rather than assumed.")
    if not all_ok and not zero_coverage:
        print("  FAIL -- at least one factor is applied unevenly across its cells.")
        print("  Do NOT run the sweep. The affected contrast would be confounded")
        print("  with whatever differs between the high- and low-coverage cells,")
        print("  and the resulting S_i would be an artifact of the pipeline rather")
        print("  than a property of the model.")
    if all_ok:
        print("  PASS -- every factor is applied at a comparable rate across the")
        print("  cells where it is switched on. Contrasts are not confounded by")
        print("  differential treatment coverage. Note that uniformly low coverage")
        print("  still ATTENUATES an effect (it does not bias it); read a small")
        print("  S_i against the coverage rates above.")
    return all_ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True,
                    help="JSON manifest produced by orchestrator.build_manifest()")
    ap.add_argument("--min-coverage", type=float, default=0.30,
                    help="Minimum MEAN application rate for a factor across "
                         "its cells (default 0.30). Guards against the case "
                         "where near-zero coverage passes a spread test.")
    ap.add_argument("--max-spread", type=float, default=0.10,
                    help="Max tolerated difference in application rate across "
                         "cells sharing a factor level (default 0.10)")
    args = ap.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)

    by_cond = audit(manifest)
    ok = print_report(by_cond, args.max_spread, args.min_coverage)
    sys.exit(0 if ok else 1)