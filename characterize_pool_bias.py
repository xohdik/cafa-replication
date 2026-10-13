"""
Characterize the SELECTION BIAS introduced by eligibility filtering.

Requiring every sample to clear every treatment in every cell buys balanced
coverage, but at measured 12.5% retention it also selects a non-random subset:
programs short enough, simple enough, and library-free enough for a 6.7B model
to translate eight times over. Those are plausibly the programs where
memorization and lexical shortcutting behave DIFFERENTLY than on complex code,
so the restriction is not a neutral loss of statistical power -- it may shift
what the decomposition measures.

Reporting "n = 62 after filtering" is insufficient. This script quantifies how
the surviving pool differs from the corpus it was drawn from, so the paper can
state the bias in the same terms a reviewer would ask about.

Usage:
    python3 characterize_pool_bias.py --manifest manifest.json \\
        --samples rq4_samples_verified.jsonl
"""
import argparse
import json
import os
import statistics
import sys
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from synthesize import complexity_profile
from transpile import uses_untranslatable_imports


def profile_of(code: str) -> dict:
    lines = len([l for l in code.splitlines() if l.strip()])
    try:
        p = complexity_profile(code)
        cyc, depth = p.cyclomatic, p.max_depth
    except Exception:
        cyc, depth = None, None
    return {"lines": lines, "chars": len(code), "cyclomatic": cyc,
            "max_depth": depth, "n_imports": len(uses_untranslatable_imports(code))}


def summarize(profiles: list, key: str):
    vals = [p[key] for p in profiles if p[key] is not None]
    if not vals:
        return None
    return {"n": len(vals), "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "p90": sorted(vals)[int(0.9 * (len(vals) - 1))],
            "max": max(vals)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--samples", required=True)
    args = ap.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)

    rows = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    kept_idx = {s["sample_index"] for s in manifest.get("samples", [])}
    excluded = manifest.get("excluded", [])
    excl_reasons = {}
    for e in excluded:
        r = e["reason"].split(":")[0]
        excl_reasons[r] = excl_reasons.get(r, 0) + 1

    n_considered = len(kept_idx) + len(excluded)
    kept = [profile_of(rows[i]["source_code"]) for i in sorted(kept_idx) if i < len(rows)]
    dropped = [profile_of(rows[e["sample_index"]]["source_code"])
               for e in excluded if e["sample_index"] < len(rows)]

    print("=" * 70)
    print("POOL SELECTION BIAS")
    print("=" * 70)
    print(f"  considered: {n_considered}")
    print(f"  eligible:   {len(kept)}  ({len(kept)/n_considered:.1%})" if n_considered else "")
    print(f"  excluded:   {len(dropped)}")

    if excl_reasons:
        print("\n  Exclusion reasons:")
        for r, c in sorted(excl_reasons.items(), key=lambda kv: -kv[1]):
            print(f"    {c:5d}  {r}")

    print("\n" + "=" * 70)
    print("HOW THE SURVIVING POOL DIFFERS")
    print("=" * 70)
    print(f"  {'metric':<14} {'eligible':>28}   {'excluded':>28}")
    print(f"  {'':<14} {'mean / median / p90':>28}   {'mean / median / p90':>28}")
    print("  " + "-" * 74)
    for key in ("lines", "chars", "cyclomatic", "max_depth"):
        a, b = summarize(kept, key), summarize(dropped, key)
        if not a or not b:
            continue
        left = f"{a['mean']:8.1f} / {a['median']:6.1f} / {a['p90']:6.1f}"
        right = f"{b['mean']:8.1f} / {b['median']:6.1f} / {b['p90']:6.1f}"
        print(f"  {key:<14} {left:>28}   {right:>28}")

    print("\n" + "=" * 70)
    print("INTERPRETATION")
    print("=" * 70)
    a_lines, b_lines = summarize(kept, "lines"), summarize(dropped, "lines")
    if a_lines and b_lines and b_lines["median"] > 0:
        ratio = a_lines["median"] / b_lines["median"]
        print(f"  Surviving programs are {ratio:.2f}x the median length of excluded ones.")
    print("  State this in the paper's threats to validity, with these numbers.")
    print("  The claim that survives is about the decomposition ON THIS POOL:")
    print("  short, library-free programs a small model can translate. Whether")
    print("  the same S_i values hold for long, library-dependent programs is")
    print("  untested, and the filtering makes it untestable with this setup")
    print("  rather than merely unmeasured.")


if __name__ == "__main__":
    main()