"""
Prerequisite RQ A / RQ4 batch runner: runs X2 (rename) and X3 (shuffle) over
a real sample pool and reports the DISTRIBUTION of structural distances, not
just the mean -- per the finding in Section VIII of the paper, a pool
containing structurally-interchangeable-statement samples will understate
X3's true strength if you only look at the mean, since some individual swaps
are genuinely invisible to a structure-only metric even when they occurred.

Point this at your real TOSEM/EMSE corpus on the R740:

    python3 rq4_batch_check.py --samples path/to/samples.jsonl

samples.jsonl: one JSON object per line, {"source_code": "...", "repo_id": "..."}
(func_name/test_inputs not needed for this check -- it only exercises X2/X3).
"""
import argparse
import json
import random
import statistics
import sys
import os
import time
import warnings

# Real-world corpora (CodeNet etc.) contain Python 2 relics and odd literals
# that make ast.parse emit SyntaxWarning noise. Those samples are counted and
# reported as skips; the warnings themselves are just noise.
warnings.filterwarnings("ignore", category=SyntaxWarning)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "perturbations"))

from identifier_rename import obfuscate_identifiers
from ast_shuffle import shuffle_ast
from manipulation_check import order_sensitive_distance


def run_batch(samples: list, seed: int = 0, progress_every: int = 50,
               max_chars: int = 20000) -> dict:
    """
    samples: list of source code strings.
    Returns per-sample results plus distributional summary stats for both
    X2 and X3 distances, and flags samples where X2 leaked structural
    signal (should be ~0) or X3 produced a zero-distance false negative
    (the interchangeable-statement edge case).

    max_chars: samples larger than this are skipped and counted separately.
    Very large functions are rare, are not representative of the pool, and
    dominate runtime; report the skip count rather than silently including
    or silently dropping them.
    """
    rng = random.Random(seed)
    results = []
    skipped = []
    oversized = []
    t_start = time.time()

    for i, code in enumerate(samples):
        if progress_every and i and i % progress_every == 0:
            elapsed = time.time() - t_start
            rate = i / elapsed if elapsed > 0 else 0
            print(f"  ...{i}/{len(samples)} processed "
                  f"({elapsed:.1f}s, {rate:.1f}/s)", flush=True)

        if len(code) > max_chars:
            oversized.append({"index": i, "n_chars": len(code)})
            continue

        try:
            renamed, mapping = obfuscate_identifiers(code)
            shuffled, shuffle_stats = shuffle_ast(code, seed=rng.randint(0, 2**31))
        except (SyntaxError, ValueError, RecursionError) as e:
            skipped.append({"index": i, "error": f"{type(e).__name__}: {e}"})
            continue

        try:
            d_x2 = order_sensitive_distance(code, renamed, structure_only=True)
            d_x3 = order_sensitive_distance(code, shuffled, structure_only=True)
        except (SyntaxError, ValueError, RecursionError) as e:
            skipped.append({"index": i, "error": f"distance failed: {type(e).__name__}: {e}"})
            continue

        results.append({
            "index": i,
            "d_x2_rename": d_x2,
            "d_x3_shuffle": d_x3,
            "n_shuffled_blocks": shuffle_stats["n_shuffled_blocks"],
            "n_atomic_blocks": shuffle_stats["n_atomic_blocks"],
            "x2_leaked_structure": d_x2 > 0.02,
            "x3_zero_distance_despite_shuffle": (
                shuffle_stats["n_shuffled_blocks"] > 0 and d_x3 == 0.0
            ),
        })

    elapsed = time.time() - t_start

    def dist_summary(key):
        vals = [r[key] for r in results]
        if not vals:
            return None
        return {
            "mean": statistics.mean(vals),
            "median": statistics.median(vals),
            "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
            "min": min(vals),
            "max": max(vals),
        }

    n = len(results)
    n_x2_leaked = sum(1 for r in results if r["x2_leaked_structure"])
    n_x3_zero_despite_shuffle = sum(1 for r in results if r["x3_zero_distance_despite_shuffle"])
    n_no_shuffleable_blocks = sum(1 for r in results if r["n_shuffled_blocks"] == 0)

    return {
        "n_samples": len(samples),
        "n_processed": n,
        "n_skipped_syntax_error": len(skipped),
        "n_skipped_oversized": len(oversized),
        "elapsed_seconds": elapsed,
        "skipped": skipped[:20],
        "oversized": oversized[:20],
        "x2_distance_distribution": dist_summary("d_x2_rename"),
        "x3_distance_distribution": dist_summary("d_x3_shuffle"),
        "n_x2_leaked_structure": n_x2_leaked,
        "x2_leak_rate": n_x2_leaked / n if n else 0.0,
        "n_x3_zero_distance_despite_shuffle": n_x3_zero_despite_shuffle,
        "x3_false_negative_rate": n_x3_zero_despite_shuffle / n if n else 0.0,
        "n_samples_with_no_shuffleable_blocks": n_no_shuffleable_blocks,
        "n_samples_with_no_shuffleable_blocks_rate": n_no_shuffleable_blocks / n if n else 0.0,
        "per_sample": results,
    }


def print_report(report: dict):
    print(f"\nProcessed {report['n_processed']}/{report['n_samples']} samples "
          f"in {report['elapsed_seconds']:.1f}s "
          f"({report['n_skipped_syntax_error']} skipped: parse/analysis errors; "
          f"{report['n_skipped_oversized']} skipped: oversized)\n")

    if report["n_skipped_syntax_error"]:
        print("  Sample of skipped-sample errors (first few):")
        for s in report["skipped"][:3]:
            print(f"    idx {s['index']}: {s['error'][:100]}")
        print()

    print("X2 (rename) distance distribution -- should cluster near 0:")
    d = report["x2_distance_distribution"]
    if d:
        print(f"  mean={d['mean']:.4f}  median={d['median']:.4f}  "
              f"stdev={d['stdev']:.4f}  range=[{d['min']:.4f}, {d['max']:.4f}]")
    print(f"  {report['n_x2_leaked_structure']}/{report['n_processed']} samples "
          f"({report['x2_leak_rate']:.1%}) leaked structural signal (distance > 0.02) "
          f"-- these need the obfuscator investigated before trusting X2 as a clean isolator.\n")

    print("X3 (shuffle) distance distribution -- should be meaningfully > X2's:")
    d = report["x3_distance_distribution"]
    if d:
        print(f"  mean={d['mean']:.4f}  median={d['median']:.4f}  "
              f"stdev={d['stdev']:.4f}  range=[{d['min']:.4f}, {d['max']:.4f}]")
    print(f"  {report['n_x3_zero_distance_despite_shuffle']}/{report['n_processed']} samples "
          f"({report['x3_false_negative_rate']:.1%}) had a real shuffle event but zero "
          f"detectable distance (the interchangeable-statement edge case, Section VIII) "
          f"-- expected to be nonzero, not a bug, but report this rate, don't hide it.")
    print(f"  {report['n_samples_with_no_shuffleable_blocks']}/{report['n_processed']} samples "
          f"({report['n_samples_with_no_shuffleable_blocks_rate']:.1%}) had NO independent "
          f"statement blocks at all -- X3 has zero effective strength on these regardless of "
          f"metric; if this rate is high, your sample pool may be too dependency-chained for "
          f"X3 to do meaningful work and needs review before the real sweep.")

    if report["x2_distance_distribution"] and report["x3_distance_distribution"]:
        x2_mean = report["x2_distance_distribution"]["mean"]
        x3_mean = report["x3_distance_distribution"]["mean"]
        x3_median = report["x3_distance_distribution"]["median"]
        dead_rate = report["n_samples_with_no_shuffleable_blocks_rate"]

        print("\n" + "=" * 62)
        print("RQ4 VERDICT")
        print("=" * 62)

        # Test 1: X2 must not leak structural signal.
        x2_clean = report["x2_leak_rate"] < 0.05
        print(f"  [{'PASS' if x2_clean else 'FAIL'}] X2 isolates lexical only "
              f"(leak rate {report['x2_leak_rate']:.1%}, need <5%)")

        # Test 2: X3 must separate from X2 at all.
        separates = x3_mean > x2_mean
        print(f"  [{'PASS' if separates else 'FAIL'}] X3 separates from X2 "
              f"(X3 mean {x3_mean:.4f} vs X2 mean {x2_mean:.4f})")

        # Test 3 -- THE ONE THAT MATTERS: X3 must actually perturb enough of
        # the pool to carry signal. A tiny-but-nonzero mean passes test 2 while
        # being useless in practice; that is exactly the failure mode this
        # check exists to catch.
        strong_enough = x3_median > 0.02 and dead_rate < 0.50
        print(f"  [{'PASS' if strong_enough else 'FAIL'}] X3 is practically "
              f"effective (median {x3_median:.4f}, need >0.02; "
              f"{dead_rate:.1%} of pool unperturbable, need <50%)")

        print()
        if x2_clean and separates and strong_enough:
            print("  OVERALL: PASS -- operators are usable for the real sweep.")
        elif x2_clean and separates:
            print("  OVERALL: WEAK -- X3 is technically separable but too weak "
                  "to carry\n  meaningful signal on this pool. S_i(AST structure) "
                  "estimated from it\n  would be near-zero for INSTRUMENT reasons, "
                  "not because models are\n  insensitive to structure. Do not run "
                  "the sweep on this pool without\n  either (a) strengthening the "
                  "operator, or (b) reporting the ceiling\n  explicitly as a "
                  "limitation on what X3 can detect.")
        else:
            print("  OVERALL: FAIL -- investigate before trusting X2/X3.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default=None,
                         help="Path to a .jsonl file, one {'source_code': ...} object per line. "
                              "If omitted, runs on small built-in fixtures (sandbox demo only -- "
                              "point this at your real corpus on the R740).")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if args.samples:
        codes = []
        with open(args.samples) as f:
            for line in f:
                line = line.strip()
                if line:
                    codes.append(json.loads(line)["source_code"])
    else:
        print("No --samples given -- running on sandbox fixtures. "
              "Point --samples at your real TOSEM/EMSE corpus for the actual RQ4 result.\n")
        codes = [
            "def f(items):\n    total = 0\n    for x in items:\n        if x > 0:\n            total += x\n    return total",
            "def g(a, b, c):\n    if a > b:\n        if b > c:\n            return a\n        return b\n    return c",
            "def h(n):\n    result = 0\n    for i in range(n):\n        for j in range(n):\n            if i == j:\n                result += 1\n    return result",
            "def add_pairs(a, b):\n    return a + b",
            "def classify(x):\n    if x > 0:\n        return 1\n    elif x < 0:\n        return -1\n    return 0",
            "def two_inits(a, b):\n    x = 0\n    y = 0\n    x += a\n    y += b\n    return x + y",
        ]

    report = run_batch(codes, seed=args.seed)
    print_report(report)