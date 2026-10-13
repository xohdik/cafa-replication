"""
Measure X4 feasibility on a corpus BEFORE spending GPU hours on it.

Diagnosis of three real script-translation failures showed one cause is not a
prompting or model-capability issue but a hard limit: Python programs that
import stdlib modules with no JavaScript counterpart (bisect, collections,
heapq, itertools, ...) cannot be faithfully translated. The measured failure
was `import bisect` becoming `require("./bisect.js")`, a module that does not
exist.

That makes X4's ceiling a property of the CORPUS, not of the model, and it is
cheap to measure exactly. This script reports what fraction of samples are
translatable in principle, so the decision to keep, restrict, or abandon X4
rests on a number rather than on impressions from three examples.

Usage:
    python3 measure_x4_feasibility.py --samples rq4_samples_verified.jsonl
"""
import argparse
import json
import os
import sys
import warnings
from collections import Counter

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from transpile import uses_untranslatable_imports, UNTRANSLATABLE_IMPORTS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--max-lines", type=int, default=60,
                    help="Programs longer than this are counted separately: a "
                         "long source crowds the few-shot prompt and was the "
                         "cause of one observed empty-output failure.")
    args = ap.parse_args()

    rows = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))

    n = len(rows)
    blocked = Counter()
    n_clean = 0
    n_blocked_imports = 0
    n_too_long = 0
    n_both = 0

    for r in rows:
        code = r["source_code"]
        bad = uses_untranslatable_imports(code)
        long_src = len([l for l in code.splitlines() if l.strip()]) > args.max_lines
        for m in bad:
            blocked[m] += 1
        if bad and long_src:
            n_both += 1
        elif bad:
            n_blocked_imports += 1
        elif long_src:
            n_too_long += 1
        else:
            n_clean += 1

    print("=" * 66)
    print("X4 FEASIBILITY ON THIS CORPUS")
    print("=" * 66)
    print(f"  samples:                              {n}")
    print(f"  translatable in principle:            {n_clean:5d}  ({n_clean/n:.1%})")
    print(f"  blocked by untranslatable imports:    {n_blocked_imports:5d}  ({n_blocked_imports/n:.1%})")
    print(f"  blocked by length (> {args.max_lines} lines):       {n_too_long:5d}  ({n_too_long/n:.1%})")
    print(f"  blocked by both:                      {n_both:5d}  ({n_both/n:.1%})")

    if blocked:
        print("\n  Most common blocking imports:")
        for mod, cnt in blocked.most_common(12):
            print(f"    {mod:<15} {cnt:5d}  ({cnt/n:.1%})")

    usable = n_clean / n if n else 0
    print("\n" + "=" * 66)
    print("INTERPRETATION")
    print("=" * 66)
    print(f"  Upper bound on X4 coverage from corpus alone: {usable:.1%}")
    print("  (Model translation success applies ON TOP of this, so realized")
    print("   coverage will be lower.)")
    print()
    if usable >= 0.50:
        print("  X4 is viable if the pool is restricted to translatable samples.")
        print("  Add that restriction to check_sample_eligibility() so the")
        print("  restriction applies to EVERY cell, not just cross-language")
        print("  ones -- otherwise the pool differs between X4 levels and the")
        print("  language contrast is confounded with whatever else correlates")
        print("  with importing a library.")
    elif usable >= 0.20:
        print("  X4 is marginal. Restricting the pool would cost most of the")
        print("  corpus and bias it toward short, import-free programs, which")
        print("  is itself a sampling confound worth reporting. Consider a")
        print("  different operationalization of the semantic-reasoning factor.")
    else:
        print("  X4 as Python->JavaScript is NOT viable on this corpus. This is")
        print("  a property of the data, not a tuning problem: most programs")
        print("  depend on libraries with no target-language equivalent.")
        print("  Options, in order of how much they preserve the original")
        print("  construct: (a) translate to a language with closer library")
        print("  semantics; (b) translate between Python dialects (idiomatic ->")
        print("  explicit loops), a weaker but achievable semantic probe;")
        print("  (c) drop X4 to a 2^(4-1) design and report four factors.")


if __name__ == "__main__":
    main()