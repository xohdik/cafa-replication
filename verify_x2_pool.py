"""
Behaviorally verify X2 (identifier obfuscation) on a real pool.

WHY THIS EXISTS. X2 was validated only by STRUCTURAL distance: renaming
should not change AST shape, and it measured 0.0000 across 447 real samples.
That is necessary but not sufficient -- it says nothing about whether the
renamed program still RUNS. The manifest audit then showed X3 succeeding on
100% of samples in six shuffle conditions but only 62% in conditions 7 and
16, which are exactly the cells where X2 is on and X5 is off (obfuscated,
real code). Since X3's verifier reports failure when the ORIGINAL program
fails -- and after X2 the "original" is the renamed program -- the natural
hypothesis is that X2 itself breaks a fraction of real programs.

This script tests that hypothesis directly: rename, then execute both
versions against the same inputs and compare output.

Usage:
    python3 verify_x2_pool.py --samples rq4_samples_verified.jsonl --limit 100
"""
import argparse
import json
import os
import statistics
import sys
import time
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from identifier_rename import obfuscate_identifiers
from ast_shuffle import verify_script_behavior, _run_script


def run(samples: list, timeout: float = 5.0, progress_every: int = 25) -> dict:
    t0 = time.time()
    n_no_tests = 0
    n_rename_error = 0
    n_original_broken = 0
    n_ok = 0
    n_broken_by_rename = 0
    broken_examples = []

    for i, s in enumerate(samples):
        if progress_every and i and i % progress_every == 0:
            el = time.time() - t0
            print(f"  ...{i}/{len(samples)} ({el:.1f}s) "
                  f"[ok={n_ok} broken={n_broken_by_rename}]", flush=True)

        code = s["source_code"]
        stdin_cases = s.get("stdin_cases")
        if not stdin_cases:
            n_no_tests += 1
            continue

        # Does the ORIGINAL run? If not, this sample tells us nothing about X2.
        base_out, base_err = _run_script(code, stdin_cases[0], timeout)
        if base_err is not None:
            n_original_broken += 1
            continue

        try:
            renamed, mapping = obfuscate_identifiers(code)
        except Exception as e:
            n_rename_error += 1
            continue

        report = verify_script_behavior(code, renamed, stdin_cases, timeout=timeout)
        if report["passed"]:
            n_ok += 1
        else:
            n_broken_by_rename += 1
            if len(broken_examples) < 6:
                broken_examples.append({
                    "pair_id": s.get("pair_id"),
                    "problem_id": s.get("problem_id"),
                    "original": code[:500],
                    "renamed": renamed[:500],
                    "mismatch": report["mismatches"][:1],
                    "n_renamed": len(mapping),
                })

    n_tested = n_ok + n_broken_by_rename
    return {
        "n_samples": len(samples),
        "elapsed_seconds": time.time() - t0,
        "n_no_test_cases": n_no_tests,
        "n_original_broken": n_original_broken,
        "n_rename_error": n_rename_error,
        "n_tested": n_tested,
        "n_ok": n_ok,
        "n_broken_by_rename": n_broken_by_rename,
        "break_rate": (n_broken_by_rename / n_tested) if n_tested else None,
        "broken_examples": broken_examples,
    }


def print_report(r: dict):
    print("\n" + "=" * 66)
    print("X2 BEHAVIORAL VERIFICATION (identifier obfuscation)")
    print("=" * 66)
    print(f"  samples:                     {r['n_samples']}")
    print(f"  elapsed:                     {r['elapsed_seconds']:.1f}s")
    print(f"  skipped, no test case:       {r['n_no_test_cases']}")
    print(f"  skipped, original broken:    {r['n_original_broken']}   (corpus, not X2)")
    print(f"  skipped, rename raised:      {r['n_rename_error']}")
    print()
    print(f"  TESTED:                      {r['n_tested']}")
    print(f"    behavior preserved:        {r['n_ok']}")
    print(f"    BROKEN BY RENAMING:        {r['n_broken_by_rename']}")
    if r["break_rate"] is not None:
        print(f"    break rate:                {r['break_rate']:.1%}")

    if r["broken_examples"]:
        print("\n" + "=" * 66)
        print("EXAMPLES BROKEN BY RENAMING")
        print("=" * 66)
        for ex in r["broken_examples"][:3]:
            print(f"\n--- {ex['pair_id']} (problem {ex['problem_id']}, "
                  f"{ex['n_renamed']} names renamed) ---")
            print("ORIGINAL:"); print(ex["original"][:320])
            print("RENAMED:");  print(ex["renamed"][:320])
            print("MISMATCH:", str(ex["mismatch"])[:400])

    print("\n" + "=" * 66)
    print("INTERPRETATION")
    print("=" * 66)
    br = r["break_rate"]
    if br is None:
        print("  Nothing testable. Check that samples carry stdin_cases.")
    elif br == 0:
        print("  X2 preserves behavior on every tested sample. If X3 coverage is")
        print("  still uneven between obfuscated and non-obfuscated cells, the")
        print("  cause lies elsewhere -- look at the interaction between renaming")
        print("  and X3's own dependency analysis, not at X2 in isolation.")
    else:
        print(f"  X2 breaks {br:.1%} of programs it renames. This invalidates X2 as")
        print("  a clean lexical-only intervention: a model scored on these is")
        print("  penalized for broken code, not for losing identifier semantics,")
        print("  and S_i(lexical) becomes an artifact. Inspect the examples above,")
        print("  fix the obfuscator, and re-run before the sweep. Note the")
        print("  structural distance metric CANNOT see this -- renaming leaves AST")
        print("  shape untouched by construction, which is why it measured 0.0000")
        print("  while a third of programs were being broken.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    samples = []
    with open(args.samples) as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    if args.limit:
        samples = samples[:args.limit]

    r = run(samples, timeout=args.timeout)
    print_report(r)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(r, f, indent=2)
        print(f"\nFull results written to {args.json_out}")