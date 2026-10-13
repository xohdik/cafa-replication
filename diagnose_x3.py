"""
Diagnostic: WHY is X3 failing to perturb this corpus?

Two rounds of fixes moved the unperturbable rate only 74.3% -> 73.2%, which
means the bottleneck is not the dependency analysis. This script measures the
actual cause instead of guessing again. Run it on the same .jsonl the RQ4
batch check uses:

    python3 diagnose_x3.py --samples rq4_samples.jsonl

It reports:
  1. STRUCTURE: how many samples define functions at all vs. are top-level
     scripts. BodyShuffler only visits FunctionDef, so a corpus of top-level
     scripts is unperturbable by construction regardless of the analysis.
  2. BODY SIZES: how many statements are actually available to reorder.
     A body of 1 statement can never be shuffled.
  3. BLOCKING REASONS: for every consecutive statement pair, a histogram of
     why it was refused (barrier / both-impure / def-use hazard).
"""
import argparse
import ast
import json
import sys
import os
import warnings
from collections import Counter

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from ast_shuffle import analyze, is_barrier


def classify_pair(a: ast.stmt, b: ast.stmt) -> str:
    """Return the FIRST reason this pair can't be reordered, or 'independent'."""
    if is_barrier(a) or is_barrier(b):
        return "barrier (return/break/import/...)"
    A, B = analyze(a), analyze(b)
    if A.has_side_effects and B.has_side_effects:
        return "both have impure calls (input/print/mutation)"
    if A.defs & (B.uses | B.defs):
        return "def-use hazard (a writes what b touches)"
    if B.defs & (A.uses | A.defs):
        return "use-def hazard (b writes what a touches)"
    return "independent"


def diagnose(codes: list) -> dict:
    n_parse_fail = 0
    n_with_funcdef = 0
    n_toplevel_only = 0
    module_body_sizes = []
    func_body_sizes = []
    pair_reasons = Counter()
    pair_reasons_toplevel = Counter()
    pair_reasons_infunc = Counter()

    for code in codes:
        try:
            tree = ast.parse(code)
        except (SyntaxError, ValueError, RecursionError):
            n_parse_fail += 1
            continue

        funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        if funcs:
            n_with_funcdef += 1
            for f in funcs:
                func_body_sizes.append(len(f.body))
                for i in range(len(f.body) - 1):
                    r = classify_pair(f.body[i], f.body[i + 1])
                    pair_reasons[r] += 1
                    pair_reasons_infunc[r] += 1
        else:
            n_toplevel_only += 1

        module_body_sizes.append(len(tree.body))
        for i in range(len(tree.body) - 1):
            r = classify_pair(tree.body[i], tree.body[i + 1])
            pair_reasons_toplevel[r] += 1
            if not funcs:
                pair_reasons[r] += 1

    def med(xs):
        if not xs:
            return 0
        s = sorted(xs)
        return s[len(s) // 2]

    return {
        "n_codes": len(codes),
        "n_parse_fail": n_parse_fail,
        "n_with_funcdef": n_with_funcdef,
        "n_toplevel_only": n_toplevel_only,
        "median_module_body_stmts": med(module_body_sizes),
        "median_func_body_stmts": med(func_body_sizes),
        "n_funcs_seen": len(func_body_sizes),
        "pair_reasons": pair_reasons,
        "pair_reasons_infunc": pair_reasons_infunc,
        "pair_reasons_toplevel": pair_reasons_toplevel,
    }


def print_report(d: dict):
    n = d["n_codes"] - d["n_parse_fail"]
    print("=" * 66)
    print("1. STRUCTURE  -- does the corpus even have functions to shuffle?")
    print("=" * 66)
    print(f"  parsed:                    {n}/{d['n_codes']} "
          f"({d['n_parse_fail']} parse failures)")
    if n:
        print(f"  define >=1 function:       {d['n_with_funcdef']:5d} "
              f"({d['n_with_funcdef']/n:.1%})")
        print(f"  top-level script only:     {d['n_toplevel_only']:5d} "
              f"({d['n_toplevel_only']/n:.1%})   <-- X3 CANNOT TOUCH THESE")
    print(f"  functions seen in total:   {d['n_funcs_seen']}")

    print()
    print("=" * 66)
    print("2. BODY SIZES -- is there anything to reorder even in principle?")
    print("=" * 66)
    print(f"  median statements per module body:   {d['median_module_body_stmts']}")
    print(f"  median statements per function body: {d['median_func_body_stmts']}")
    print("  (a body of 1 statement is unshuffleable by definition)")

    def hist(title, counter):
        total = sum(counter.values())
        print(f"\n  {title}  (n={total} consecutive pairs)")
        if not total:
            print("    (none)")
            return
        for reason, cnt in counter.most_common():
            bar = "#" * int(40 * cnt / total)
            print(f"    {cnt:6d} ({cnt/total:5.1%}) {bar} {reason}")

    print()
    print("=" * 66)
    print("3. BLOCKING REASONS -- when there IS a pair, why is it refused?")
    print("=" * 66)
    hist("Pairs X3 actually evaluates (function bodies, or module if no funcs)",
         d["pair_reasons"])
    hist("Function-body pairs only", d["pair_reasons_infunc"])
    hist("Module-level pairs only (currently NOT shuffled by BodyShuffler)",
         d["pair_reasons_toplevel"])

    print()
    print("=" * 66)
    print("INTERPRETATION")
    print("=" * 66)
    if n and d["n_toplevel_only"] / n > 0.4:
        print("  -> DOMINANT CAUSE: most samples are top-level scripts with no")
        print("     function definitions. BodyShuffler only implements")
        print("     visit_FunctionDef, so these are never touched. Fix is to")
        print("     shuffle ast.Module bodies too, NOT to loosen the dependency")
        print("     analysis (which is already correct).")
    elif d["pair_reasons"].get("independent", 0) == 0 and sum(d["pair_reasons"].values()):
        print("  -> DOMINANT CAUSE: real dependency chains. Look at the")
        print("     histogram above for which hazard dominates. If it is")
        print("     'both have impure calls', the pure-call whitelist may need")
        print("     extending; if it is def-use hazards, the corpus is genuinely")
        print("     sequential and X3's ceiling should be reported as a")
        print("     limitation rather than engineered around.")
    else:
        print("  -> Mixed. Read the histograms above before changing anything.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True, help="Path to the .jsonl sample file")
    ap.add_argument("--show", type=int, default=2,
                    help="Print this many example top-level-script samples")
    args = ap.parse_args()

    codes = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                codes.append(json.loads(line)["source_code"])

    d = diagnose(codes)
    print_report(d)

    if args.show:
        print()
        print("=" * 66)
        print(f"EXAMPLE SAMPLES WITH NO FUNCTION DEF (first {args.show})")
        print("=" * 66)
        shown = 0
        for c in codes:
            if shown >= args.show:
                break
            try:
                t = ast.parse(c)
            except Exception:
                continue
            if not [x for x in ast.walk(t) if isinstance(x, ast.FunctionDef)]:
                print(f"\n--- example {shown + 1} ---")
                print(c[:600])
                shown += 1