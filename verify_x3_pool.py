"""
Run X3 (AST shuffle) across a pool that carries CodeNet test cases, verifying
each shuffle by execution. This answers the question the structural-distance
metric CANNOT answer: how often does the shuffle silently change behavior?

The distance metric in rq4_batch_check.py measures whether X3 perturbed the
structure. This measures whether X3 preserved the semantics. Both are needed:
a perturbation that is structurally strong but semantically wrong is worse
than useless, because the model then gets scored on broken programs and the
resulting S_i(structure) is an artifact.

Usage:
    python3 verify_x3_pool.py --samples rq4_samples_verified.jsonl
    python3 verify_x3_pool.py --samples rq4_samples_verified.jsonl --limit 100
"""
import argparse
import json
import random
import statistics
import sys
import os
import time
import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from ast_shuffle import shuffle_ast, verify_script_behavior
from manipulation_check import order_sensitive_distance


def run(samples: list, seed: int = 0, timeout: float = 5.0,
        progress_every: int = 25) -> dict:
    rng = random.Random(seed)
    t0 = time.time()

    n_no_tests = 0
    n_no_shuffle = 0
    n_verified_ok = 0
    n_corrupted = 0
    n_original_broken = 0
    n_error = 0
    distances_verified = []
    corrupted_examples = []

    for i, s in enumerate(samples):
        if progress_every and i and i % progress_every == 0:
            el = time.time() - t0
            print(f"  ...{i}/{len(samples)} ({el:.1f}s, {i/el:.1f}/s) "
                  f"[ok={n_verified_ok} corrupt={n_corrupted}]", flush=True)

        code = s["source_code"]
        stdin_cases = s.get("stdin_cases")
        if not stdin_cases:
            n_no_tests += 1
            continue

        try:
            shuffled, stats = shuffle_ast(code, seed=rng.randint(0, 2**31))
        except Exception:
            n_error += 1
            continue

        if stats["n_shuffled_blocks"] == 0:
            n_no_shuffle += 1
            continue

        report = verify_script_behavior(code, shuffled, stdin_cases, timeout=timeout)

        if report["passed"]:
            n_verified_ok += 1
            try:
                distances_verified.append(
                    order_sensitive_distance(code, shuffled, structure_only=True))
            except Exception:
                pass
        else:
            reasons = [m.get("reason", "") for m in report["mismatches"]]
            if any(r.startswith("original failed") for r in reasons):
                # The ORIGINAL program doesn't run against this test case.
                # Not an X3 bug -- a corpus/test-case mismatch. Counted apart
                # so it can't be mistaken for shuffle corruption.
                n_original_broken += 1
            else:
                n_corrupted += 1
                if len(corrupted_examples) < 5:
                    corrupted_examples.append({
                        "pair_id": s.get("pair_id"),
                        "problem_id": s.get("problem_id"),
                        "original": code[:400],
                        "shuffled": shuffled[:400],
                        "mismatches": report["mismatches"][:2],
                    })

    elapsed = time.time() - t0
    n_attempted = n_verified_ok + n_corrupted
    return {
        "n_samples": len(samples),
        "elapsed_seconds": elapsed,
        "n_no_test_cases": n_no_tests,
        "n_no_shuffle_possible": n_no_shuffle,
        "n_shuffle_attempted_and_testable": n_attempted,
        "n_verified_ok": n_verified_ok,
        "n_corrupted": n_corrupted,
        "n_original_broken_on_test": n_original_broken,
        "n_error": n_error,
        "corruption_rate": (n_corrupted / n_attempted) if n_attempted else None,
        "distance_when_verified": {
            "mean": statistics.mean(distances_verified) if distances_verified else None,
            "median": statistics.median(distances_verified) if distances_verified else None,
            "max": max(distances_verified) if distances_verified else None,
            "n": len(distances_verified),
        },
        "corrupted_examples": corrupted_examples,
    }


def print_report(r: dict):
    print("\n" + "=" * 66)
    print("X3 BEHAVIORAL VERIFICATION")
    print("=" * 66)
    print(f"  samples:                          {r['n_samples']}")
    print(f"  elapsed:                          {r['elapsed_seconds']:.1f}s")
    print(f"  skipped, no test case:            {r['n_no_test_cases']}")
    print(f"  skipped, nothing to shuffle:      {r['n_no_shuffle_possible']}")
    print(f"  skipped, original fails its test: {r['n_original_broken_on_test']}"
          "   (corpus issue, not X3)")
    print(f"  errors:                           {r['n_error']}")
    print()
    print(f"  SHUFFLED AND TESTABLE:            {r['n_shuffle_attempted_and_testable']}")
    print(f"    verified behavior-preserving:   {r['n_verified_ok']}")
    print(f"    SILENTLY CORRUPTED:             {r['n_corrupted']}")
    if r["corruption_rate"] is not None:
        print(f"    corruption rate:                {r['corruption_rate']:.1%}")

    d = r["distance_when_verified"]
    if d["n"]:
        print()
        print(f"  Structural distance among VERIFIED-CORRECT shuffles (n={d['n']}):")
        print(f"    mean {d['mean']:.4f}  median {d['median']:.4f}  max {d['max']:.4f}")
        print("    (this is X3's real usable perturbation strength -- distances")
        print("     from corrupted shuffles must not be counted)")

    if r["corrupted_examples"]:
        print()
        print("=" * 66)
        print("CORRUPTION EXAMPLES (inspect these -- each is an operator bug)")
        print("=" * 66)
        for ex in r["corrupted_examples"][:3]:
            print(f"\n--- {ex['pair_id']} (problem {ex['problem_id']}) ---")
            print("ORIGINAL:"); print(ex["original"][:300])
            print("SHUFFLED:"); print(ex["shuffled"][:300])
            print("MISMATCH:", ex["mismatches"][:1])

    print()
    print("=" * 66)
    print("INTERPRETATION")
    print("=" * 66)
    cr = r["corruption_rate"]
    if cr is None:
        print("  No verifiable shuffles. Check that the join produced stdin_cases.")
    elif cr == 0:
        print("  No corruption detected. Note this is single-test-case evidence,")
        print("  not proof -- report it as an upper bound on how much corruption")
        print("  a one-input check can rule out.")
    elif cr < 0.02:
        print(f"  Low corruption ({cr:.1%}). Use shuffle_and_verify_script() in the")
        print("  sweep so these auto-revert rather than entering the dataset.")
    else:
        print(f"  HIGH corruption ({cr:.1%}). Do not run the sweep until the")
        print("  examples above are diagnosed -- every corrupted sample injects")
        print("  'model cannot handle broken code' signal into S_i(structure).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--limit", type=int, default=None,
                    help="Only process the first N samples (subprocess execution "
                         "is slow; start small)")
    ap.add_argument("--seed", type=int, default=0)
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

    r = run(samples, seed=args.seed, timeout=args.timeout)
    print_report(r)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(r, f, indent=2)
        print(f"\nFull results written to {args.json_out}")